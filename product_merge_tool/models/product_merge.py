import logging
from psycopg2 import sql as psql
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SKIP_TABLES = {
    'product_merge_tool_line_product_template_rel',
}


class ProductMergeTool(models.Model):
    _name = 'product.merge.tool'
    _description = 'Product Merge Tool'
    _order = 'create_date desc'

    name = fields.Char(default=lambda self: _('New'), readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scanning', 'Scanning'),
        ('ready', 'Ready'),
        ('merging', 'Merging'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], default='draft', readonly=True)
    log = fields.Text(readonly=True)
    merge_line_ids = fields.One2many('product.merge.tool.line', 'merge_id', readonly=True)
    total_groups = fields.Integer(compute='_compute_stats', store=True)
    total_duplicates = fields.Integer(compute='_compute_stats', store=True)
    total_merged = fields.Integer(compute='_compute_stats', store=True)

    @api.depends('merge_line_ids', 'merge_line_ids.state')
    def _compute_stats(self):
        for rec in self:
            rec.total_groups = len(rec.merge_line_ids)
            rec.total_duplicates = sum(rec.merge_line_ids.mapped('duplicate_count'))
            rec.total_merged = len(rec.merge_line_ids.filtered(lambda l: l.state == 'merged'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('product.merge.tool') or _('New')
        return super().create(vals_list)

    def _append_log(self, msg):
        self.log = (self.log or '') + msg + '\n'
        _logger.info(msg)

    def action_scan(self):
        self.ensure_one()
        self.state = 'scanning'
        self.merge_line_ids.unlink()
        self.log = ''

        self._append_log(_('=== Step 1: Deactivate orphan templates (no active variants) ==='))
        self._deactivate_orphan_templates()

        self._append_log(_('=== Phase 1: Scanning templates by Internal Reference ==='))
        self._scan_templates_by_ref()

        self._append_log(_('=== Phase 2: Scanning templates by English Name ==='))
        self._scan_templates_by_name('en_US')

        self._append_log(_('=== Phase 3: Scanning templates by Arabic Name ==='))
        self._scan_templates_by_name('ar_001')

        self.state = 'ready'
        total = len(self.merge_line_ids)
        self._append_log(_('Scan complete. Found %s groups to merge.') % total)

    def _deactivate_orphan_templates(self):
        self.env.cr.execute("""
            UPDATE product_template pt SET active = false
            WHERE pt.active = true
              AND NOT EXISTS (
                  SELECT 1 FROM product_product pp
                  WHERE pp.product_tmpl_id = pt.id AND pp.active = true
              )
        """)
        count = self.env.cr.rowcount
        self._append_log(_('Deactivated %s orphan templates.') % count)

    def _get_already_grouped_tmpl(self):
        already = set()
        for line in self.merge_line_ids:
            already.update(line.template_ids.ids)
        return already

    def _scan_templates_by_ref(self):
        self.env.cr.execute("""
            SELECT LOWER(TRIM(pp.default_code)),
                   array_agg(DISTINCT pt.id ORDER BY pt.id)
            FROM product_product pp
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            WHERE pp.default_code IS NOT NULL
              AND TRIM(pp.default_code) != ''
              AND pt.active = true
            GROUP BY LOWER(TRIM(pp.default_code))
            HAVING count(DISTINCT pt.id) > 1
        """)
        groups = self.env.cr.fetchall()
        count = 0
        for ref, tmpl_ids in groups:
            self.env['product.merge.tool.line'].create({
                'merge_id': self.id,
                'match_type': 'ref',
                'match_key': ref,
                'template_ids': [(6, 0, tmpl_ids)],
                'duplicate_count': len(tmpl_ids),
            })
            count += 1
        self._append_log(_('Found %s groups by internal reference.') % count)

    def _scan_templates_by_name(self, lang):
        already_grouped = self._get_already_grouped_tmpl()
        query = """
            SELECT LOWER(TRIM(pt.name->>%s)),
                   array_agg(pt.id ORDER BY pt.id)
            FROM product_template pt
            WHERE pt.active = true
              AND pt.name->>%s IS NOT NULL
              AND TRIM(pt.name->>%s) != ''
            GROUP BY LOWER(TRIM(pt.name->>%s))
            HAVING count(*) > 1
        """
        self.env.cr.execute(query, (lang, lang, lang, lang))
        groups = self.env.cr.fetchall()
        count = 0
        for name, tmpl_ids in groups:
            remaining = [tid for tid in tmpl_ids if tid not in already_grouped]
            if len(remaining) > 1:
                self.env['product.merge.tool.line'].create({
                    'merge_id': self.id,
                    'match_type': 'name',
                    'match_key': name,
                    'template_ids': [(6, 0, remaining)],
                    'duplicate_count': len(remaining),
                })
                already_grouped.update(remaining)
                count += 1
        self._append_log(_('Found %s groups by %s name.') % (count, lang))

    def action_merge_all(self):
        self.ensure_one()
        if self.state != 'ready':
            raise UserError(_('Please scan for duplicates first.'))
        self.state = 'merging'
        self._append_log(_('=== Starting Merge Process ==='))
        lines = self.merge_line_ids.filtered(lambda l: l.state == 'pending')
        total = len(lines)
        for idx, line in enumerate(lines, 1):
            try:
                line.action_merge()
                self._append_log(_('[%s/%s] Merged group: %s') % (idx, total, line.match_key))
            except Exception as e:
                _logger.exception("Failed merging group %s", line.match_key)
                self._append_log(_('[%s/%s] FAILED group: %s - %s') % (idx, total, line.match_key, str(e)))
                line.state = 'failed'
            if idx % 50 == 0:
                self.env.cr.commit()
        self.env.cr.commit()
        self.state = 'done'
        merged = len(self.merge_line_ids.filtered(lambda l: l.state == 'merged'))
        failed = len(self.merge_line_ids.filtered(lambda l: l.state == 'failed'))
        self._append_log(_('=== Merge Complete. Merged: %s, Failed: %s ===') % (merged, failed))

    def action_reset(self):
        self.ensure_one()
        self.state = 'draft'
        self.merge_line_ids.unlink()
        self.log = ''


class ProductMergeToolLine(models.Model):
    _name = 'product.merge.tool.line'
    _description = 'Product Merge Tool Line'

    merge_id = fields.Many2one('product.merge.tool', ondelete='cascade', required=True)
    match_type = fields.Selection([
        ('ref', 'Internal Reference'),
        ('name', 'Name'),
    ])
    match_key = fields.Char()
    template_ids = fields.Many2many('product.template', string='Duplicate Templates')
    survivor_tmpl_id = fields.Many2one('product.template', string='Surviving Template')
    duplicate_count = fields.Integer()
    state = fields.Selection([
        ('pending', 'Pending'),
        ('merged', 'Merged'),
        ('failed', 'Failed'),
    ], default='pending')

    def _choose_survivor_tmpl(self, templates):
        for t in templates:
            has_active_variant = self.env['product.product'].search_count([
                ('product_tmpl_id', '=', t.id), ('active', '=', True)
            ])
            if has_active_variant:
                variants = self.env['product.product'].search([
                    ('product_tmpl_id', '=', t.id), ('active', '=', True)
                ])
                for v in variants:
                    if v.is_appointment_service or v.is_appointment_package:
                        return t
        for t in templates:
            has_active_variant = self.env['product.product'].search_count([
                ('product_tmpl_id', '=', t.id), ('active', '=', True)
            ])
            if has_active_variant:
                return t
        return templates[0]

    def _get_fk_references(self, table_name):
        self.env.cr.execute("""
            SELECT DISTINCT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = %s
              AND tc.table_name != %s
        """, (table_name, table_name))
        return self.env.cr.fetchall()

    def _get_table_columns(self, table_name):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """, (table_name,))
        return [r[0] for r in self.env.cr.fetchall()]

    def _is_m2m_table(self, table_name):
        cols = self._get_table_columns(table_name)
        return len(cols) == 2

    def _reassign_one_ref(self, ref_table, ref_column, old_ids, new_id):
        if ref_table in SKIP_TABLES:
            return
        t = psql.Identifier(ref_table)
        c = psql.Identifier(ref_column)
        old_tuple = tuple(old_ids)

        self.env.cr.execute("SAVEPOINT merge_ref_sp")
        try:
            if self._is_m2m_table(ref_table):
                cols = self._get_table_columns(ref_table)
                other_col = [col for col in cols if col != ref_column]
                if other_col:
                    oc = psql.Identifier(other_col[0])
                    self.env.cr.execute(
                        psql.SQL("DELETE FROM {t} WHERE {c} IN %s AND {oc} IN (SELECT {oc} FROM {t} WHERE {c} = %s)")
                        .format(t=t, c=c, oc=oc),
                        (old_tuple, new_id)
                    )
                self.env.cr.execute(
                    psql.SQL("UPDATE {t} SET {c} = %s WHERE {c} IN %s").format(t=t, c=c),
                    (new_id, old_tuple)
                )
            else:
                self.env.cr.execute(
                    psql.SQL("UPDATE {t} SET {c} = %s WHERE {c} IN %s").format(t=t, c=c),
                    (new_id, old_tuple)
                )
            self.env.cr.execute("RELEASE SAVEPOINT merge_ref_sp")
        except Exception as e:
            _logger.warning("Reassign failed %s.%s, trying delete: %s", ref_table, ref_column, e)
            self.env.cr.execute("ROLLBACK TO SAVEPOINT merge_ref_sp")
            self.env.cr.execute("SAVEPOINT merge_ref_sp2")
            try:
                self.env.cr.execute(
                    psql.SQL("DELETE FROM {t} WHERE {c} IN %s").format(t=t, c=c),
                    (old_tuple,)
                )
                self.env.cr.execute("RELEASE SAVEPOINT merge_ref_sp2")
            except Exception as e2:
                _logger.warning("Delete also failed %s.%s: %s", ref_table, ref_column, e2)
                self.env.cr.execute("ROLLBACK TO SAVEPOINT merge_ref_sp2")

    def _reassign_references(self, model_table, old_ids, new_id):
        if not old_ids:
            return
        fk_refs = self._get_fk_references(model_table)
        for ref_table, ref_column in fk_refs:
            self._reassign_one_ref(ref_table, ref_column, old_ids, new_id)

    def action_merge(self):
        self.ensure_one()
        templates = self.template_ids.filtered('active')
        if len(templates) < 2:
            self.state = 'merged'
            return

        survivor_tmpl = self._choose_survivor_tmpl(templates)
        dup_templates = templates - survivor_tmpl

        all_products = self.env['product.product'].with_context(active_test=False).search([
            ('product_tmpl_id', 'in', templates.ids)
        ])

        has_service = any(all_products.mapped('is_appointment_service'))
        has_package = any(all_products.mapped('is_appointment_package'))

        survivor_products = all_products.filtered(lambda p: p.product_tmpl_id == survivor_tmpl)
        survivor_pp = survivor_products.filtered('active')
        if not survivor_pp:
            survivor_pp = survivor_products[:1]
        survivor_pp_id = survivor_pp[0].id if survivor_pp else None

        dup_products = all_products.filtered(lambda p: p.product_tmpl_id != survivor_tmpl)
        dup_pp_ids = dup_products.ids

        if survivor_pp_id and dup_pp_ids:
            self._reassign_references('product_product', dup_pp_ids, survivor_pp_id)

        dup_tmpl_ids = dup_templates.ids
        self._reassign_references('product_template', dup_tmpl_ids, survivor_tmpl.id)

        if survivor_pp_id:
            vals = {}
            if has_service:
                vals['is_appointment_service'] = True
            if has_package:
                vals['is_appointment_package'] = True
            if vals:
                set_clause = ', '.join('%s = %%s' % k for k in vals)
                self.env.cr.execute(
                    "UPDATE product_product SET %s WHERE id = %%s" % set_clause,
                    list(vals.values()) + [survivor_pp_id]
                )

        for pp in dup_products:
            self.env.cr.execute(
                "UPDATE product_product SET active = false WHERE id = %s", (pp.id,)
            )

        for tmpl in dup_templates:
            self.env.cr.execute(
                "UPDATE product_template SET active = false WHERE id = %s", (tmpl.id,)
            )

        self.survivor_tmpl_id = survivor_tmpl.id
        self.state = 'merged'
