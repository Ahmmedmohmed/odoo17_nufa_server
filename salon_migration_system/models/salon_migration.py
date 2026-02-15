# -*- coding: utf-8 -*-

import ssl
import xmlrpc.client
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SalonMigration(models.Model):
    _name = 'salon.migration'
    _description = 'Salon Data Migration'

    name = fields.Char(string='Name', required=True)
    url = fields.Char(string='URL', required=True)
    database = fields.Char(string='Database', required=True)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='State', default='draft')
    log = fields.Text(string='Log', readonly=True)
    migration_line_ids = fields.One2many('salon.migration.line', 'migration_id', string='Migration Lines', readonly=True)

    def _get_xmlrpc_connection(self):
        try:
            url = self.url.rstrip('/')
            use_ssl = url.startswith('https')
            if use_ssl:
                context = ssl.create_default_context()
                transport_common = xmlrpc.client.SafeTransport(context=context)
                transport_obj = xmlrpc.client.SafeTransport(context=context)
            else:
                transport_common = xmlrpc.client.Transport()
                transport_obj = xmlrpc.client.Transport()
            common = xmlrpc.client.ServerProxy(
                f'{url}/xmlrpc/2/common',
                transport=transport_common,
                allow_none=True,
            )
            uid = common.authenticate(self.database, self.username, self.password, {})
            if not uid:
                raise UserError(_('Authentication failed. Please check your credentials.'))
            models_proxy = xmlrpc.client.ServerProxy(
                f'{url}/xmlrpc/2/object',
                transport=transport_obj,
                allow_none=True,
            )
            return uid, models_proxy
        except xmlrpc.client.Fault as e:
            raise UserError(_('XML-RPC Error: %s') % str(e))
        except Exception as e:
            raise UserError(_('Connection Error: %s') % str(e))

    def action_test_connection(self):
        self.ensure_one()
        uid, _proxy = self._get_xmlrpc_connection()
        self.write({
            'state': 'connected',
            'log': 'Connection successful. UID: %s' % uid,
        })

    def _append_log(self, message):
        self.log = (self.log or '') + '\n' + message
        _logger.info(message)

    def _get_or_create_record(self, model, domain, vals):
        existing = self.env[model].search(domain, limit=1)
        if existing:
            return existing
        return self.env[model].create(vals)

    def _resolve_many2one(self, model, remote_id, uid, models_proxy, name_field='name'):
        if not remote_id:
            return False
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            model, 'read', [remote_id[0]], {'fields': [name_field]}
        )
        if not remote_data:
            return False
        remote_name = remote_data[0].get(name_field)
        if not remote_name:
            return False
        local = self.env[model].search([(name_field, '=', remote_name)], limit=1)
        if not local:
            try:
                local = self.env[model].create({name_field: remote_name})
                self._append_log('Created %s: %s' % (model, remote_name))
            except Exception as e:
                self._append_log('Failed to create %s "%s": %s' % (model, remote_name, str(e)))
                return False
        return local.id

    def _resolve_company(self, remote_id, uid, models_proxy):
        if not remote_id:
            return self.env.company.id
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'res.company', 'read', [remote_id[0]], {'fields': ['name']}
        )
        if not remote_data:
            return self.env.company.id
        remote_name = remote_data[0].get('name')
        local = self.env['res.company'].search([('name', '=', remote_name)], limit=1)
        if not local:
            local = self.env['res.company'].create({'name': remote_name})
            self._append_log('Created company: %s' % remote_name)
        return local.id

    def _resolve_department(self, remote_id, uid, models_proxy):
        if not remote_id:
            return False
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'hr.department', 'read', [remote_id[0]], {'fields': ['name']}
        )
        if not remote_data:
            return False
        remote_name = remote_data[0].get('name')
        local = self.env['hr.department'].search([('name', '=', remote_name)], limit=1)
        if not local:
            try:
                local = self.env['hr.department'].create({
                    'name': remote_name,
                    'is_appointment_department': True,
                })
                self._append_log('Created department: %s' % remote_name)
            except Exception as e:
                self._append_log('Failed to create department "%s": %s' % (remote_name, str(e)))
                return False
        return local.id

    def _resolve_currency(self, remote_id, uid, models_proxy):
        if not remote_id:
            return self.env.company.currency_id.id
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'res.currency', 'read', [remote_id[0]], {'fields': ['name']}
        )
        if not remote_data:
            return self.env.company.currency_id.id
        remote_name = remote_data[0].get('name')
        local = self.env['res.currency'].search([('name', '=', remote_name)], limit=1)
        if local:
            return local.id
        return self.env.company.currency_id.id

    def _resolve_categ_id(self, remote_id, uid, models_proxy):
        if not remote_id:
            return self.env.ref('product.product_category_all').id
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'product.category', 'read', [remote_id[0]], {'fields': ['name']}
        )
        if not remote_data:
            return self.env.ref('product.product_category_all').id
        remote_name = remote_data[0].get('name')
        local = self.env['product.category'].search([('name', '=', remote_name)], limit=1)
        if not local:
            local = self.env['product.category'].create({'name': remote_name})
            self._append_log('Created product category: %s' % remote_name)
        return local.id

    def _resolve_uom_id(self, remote_id, uid, models_proxy):
        if not remote_id:
            return self.env.ref('uom.product_uom_unit').id
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'uom.uom', 'read', [remote_id[0]], {'fields': ['name']}
        )
        if not remote_data:
            return self.env.ref('uom.product_uom_unit').id
        remote_name = remote_data[0].get('name')
        local = self.env['uom.uom'].search([('name', '=', remote_name)], limit=1)
        if local:
            return local.id
        return self.env.ref('uom.product_uom_unit').id

    def _resolve_pos_categ_ids(self, remote_ids, uid, models_proxy):
        if not remote_ids:
            return []
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'pos.category', 'read', remote_ids, {'fields': ['name']}
        )
        local_ids = []
        for rec in remote_data:
            local = self.env['pos.category'].search([('name', '=', rec['name'])], limit=1)
            if not local:
                local = self.env['pos.category'].create({'name': rec['name']})
                self._append_log('Created POS category: %s' % rec['name'])
            local_ids.append(local.id)
        return local_ids

    def _get_unique_barcode(self, barcode):
        if not barcode:
            return False
        existing = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)
        if existing:
            return False
        return barcode

    def _resolve_taxes(self, remote_ids, uid, models_proxy):
        if not remote_ids:
            return []
        remote_data = models_proxy.execute_kw(
            self.database, uid, self.password,
            'account.tax', 'read', remote_ids, {'fields': ['name', 'type_tax_use', 'amount']}
        )
        local_ids = []
        for rec in remote_data:
            local = self.env['account.tax'].search([
                ('name', '=', rec['name']),
                ('type_tax_use', '=', rec.get('type_tax_use', 'sale')),
            ], limit=1)
            if local:
                local_ids.append(local.id)
        return local_ids

    def action_migrate(self):
        self.ensure_one()
        self.write({'log': '', 'state': 'draft'})
        self.migration_line_ids.unlink()

        try:
            uid, models_proxy = self._get_xmlrpc_connection()
            self.write({'state': 'connected'})
            self._append_log('Connected to %s' % self.url)

            pos_categ_map = {}
            product_map = {}

            self._migrate_pos_categories(uid, models_proxy, pos_categ_map)
            self._migrate_products(uid, models_proxy, product_map, pos_categ_map)
            self._migrate_price_plans(uid, models_proxy, product_map)
            self._migrate_package_lines(uid, models_proxy, product_map)
            self._migrate_product_components(uid, models_proxy, product_map)

            self.write({'state': 'done'})
            self._append_log('Migration completed successfully.')

        except Exception as e:
            self.write({'state': 'failed'})
            self._append_log('Migration failed: %s' % str(e))
            raise UserError(_('Migration failed: %s') % str(e))

    def _migrate_pos_categories(self, uid, models_proxy, pos_categ_map):
        self._append_log('--- Migrating POS Categories ---')

        categ_fields_sets = [
            ['name', 'parent_id', 'sequence', 'image_128', 'is_appointment_category', 'image'],
            ['name', 'parent_id', 'sequence', 'image_128', 'is_appointment_category'],
            ['name', 'parent_id', 'sequence', 'image_128'],
            ['name', 'parent_id', 'sequence'],
        ]

        remote_categs = None
        remote_categ_ids = None
        try:
            remote_categ_ids = models_proxy.execute_kw(
                self.database, uid, self.password,
                'pos.category', 'search',
                [[]]
            )
        except Exception as e:
            self._append_log('Could not fetch POS categories from remote database: %s' % str(e))
            return

        if not remote_categ_ids:
            self._append_log('No POS categories found on remote database.')
            return

        for categ_fields in categ_fields_sets:
            try:
                remote_categs = models_proxy.execute_kw(
                    self.database, uid, self.password,
                    'pos.category', 'read',
                    [remote_categ_ids],
                    {'fields': categ_fields}
                )
                break
            except Exception:
                continue

        if remote_categs is None:
            self._append_log('Could not read POS categories from remote database.')
            return

        self._append_log('Found %d POS categories to migrate.' % len(remote_categs))

        remote_categ_dict = {rc['id']: rc for rc in remote_categs}

        def get_or_create_categ(remote_id):
            if remote_id in pos_categ_map:
                return pos_categ_map[remote_id]

            rc = remote_categ_dict.get(remote_id)
            if not rc:
                return False

            local_parent_id = False
            if rc.get('parent_id'):
                local_parent_id = get_or_create_categ(rc['parent_id'][0])

            local = self.env['pos.category'].search([
                ('name', '=', rc['name']),
                ('parent_id', '=', local_parent_id or False),
            ], limit=1)

            if local:
                pos_categ_map[remote_id] = local.id
                self._create_migration_line('pos.category', remote_id, local.id, rc['name'], 'skipped')
                self._append_log('Skipped POS category (already exists): %s' % rc['name'])
            else:
                vals = {
                    'name': rc['name'],
                    'parent_id': local_parent_id or False,
                    'sequence': rc.get('sequence', 10),
                }
                if rc.get('image_128'):
                    vals['image_128'] = rc['image_128']
                if rc.get('is_appointment_category') is not None:
                    vals['is_appointment_category'] = rc['is_appointment_category']
                if rc.get('image'):
                    vals['image'] = rc['image']
                local = self.env['pos.category'].create(vals)
                pos_categ_map[remote_id] = local.id
                self._create_migration_line('pos.category', remote_id, local.id, rc['name'], 'created')
                self._append_log('Created POS category: %s' % rc['name'])

            return pos_categ_map[remote_id]

        for rc in remote_categs:
            try:
                get_or_create_categ(rc['id'])
            except Exception as e:
                self._append_log('Error migrating POS category %s: %s' % (rc.get('name', rc['id']), str(e)))

    def _migrate_products(self, uid, models_proxy, product_map, pos_categ_map):
        self._append_log('--- Migrating Products ---')

        product_fields_sets = [
            [
                'name', 'default_code', 'list_price', 'standard_price',
                'type', 'categ_id', 'uom_id', 'uom_po_id',
                'is_appointment_service', 'is_appointment_package',
                'sale_ok', 'purchase_ok', 'active', 'barcode',
                'description', 'description_sale', 'description_purchase',
                'pos_categ_ids', 'available_in_pos',
                'weight', 'volume', 'image_1920',
                'taxes_id', 'supplier_taxes_id',
                'avg_rating', 'top', 'price_after_discount',
                'ar_name', 'ar_description',
            ],
            [
                'name', 'default_code', 'list_price', 'standard_price',
                'type', 'categ_id', 'uom_id', 'uom_po_id',
                'is_appointment_service', 'is_appointment_package',
                'sale_ok', 'purchase_ok', 'active', 'barcode',
                'description', 'description_sale',
                'pos_categ_ids', 'available_in_pos',
                'weight', 'volume', 'image_1920',
                'taxes_id', 'supplier_taxes_id',
            ],
            [
                'name', 'default_code', 'list_price', 'standard_price',
                'type', 'categ_id', 'uom_id', 'uom_po_id',
                'is_appointment_service', 'is_appointment_package',
                'sale_ok', 'purchase_ok', 'active', 'barcode',
                'description', 'description_sale',
                'pos_categ_ids', 'available_in_pos',
            ],
            [
                'name', 'default_code', 'list_price', 'standard_price',
                'type', 'categ_id', 'uom_id', 'uom_po_id',
                'is_appointment_service', 'is_appointment_package',
                'sale_ok', 'purchase_ok', 'active', 'barcode',
                'description', 'description_sale',
                'pos_categ_id', 'available_in_pos',
            ],
        ]

        remote_products = None
        for product_fields in product_fields_sets:
            try:
                remote_ids = models_proxy.execute_kw(
                    self.database, uid, self.password,
                    'product.product', 'search',
                    [[]],
                    {'context': {'active_test': False}}
                )
                remote_products = []
                batch_size = 100
                for i in range(0, len(remote_ids), batch_size):
                    batch = models_proxy.execute_kw(
                        self.database, uid, self.password,
                        'product.product', 'read',
                        [remote_ids[i:i + batch_size]],
                        {'fields': product_fields}
                    )
                    remote_products.extend(batch)
                break
            except Exception:
                continue

        if remote_products is None:
            self._append_log('Could not fetch products from remote database.')
            return

        self._append_log('Found %d products to migrate.' % len(remote_products))

        for rp in remote_products:
            remote_id = rp['id']
            product_name = rp.get('name', '')

            existing = self.env['product.product'].search([('name', '=', product_name)], limit=1)

            categ_id = self._resolve_categ_id(rp.get('categ_id'), uid, models_proxy)
            uom_id = self._resolve_uom_id(rp.get('uom_id'), uid, models_proxy)
            uom_po_id = self._resolve_uom_id(rp.get('uom_po_id'), uid, models_proxy)

            vals = {
                'name': product_name,
                'default_code': rp.get('default_code') or False,
                'list_price': rp.get('list_price', 0.0),
                'standard_price': rp.get('standard_price', 0.0),
                'type': rp.get('type', 'consu'),
                'categ_id': categ_id,
                'uom_id': uom_id,
                'uom_po_id': uom_po_id,
                'is_appointment_service': rp.get('is_appointment_service', False),
                'is_appointment_package': rp.get('is_appointment_package', False),
                'sale_ok': rp.get('sale_ok', True),
                'purchase_ok': rp.get('purchase_ok', False),
                'active': rp.get('active', True),
                'barcode': self._get_unique_barcode(rp.get('barcode')),
                'description': rp.get('description') or False,
                'description_sale': rp.get('description_sale') or False,
            }

            if rp.get('description_purchase'):
                vals['description_purchase'] = rp['description_purchase']

            if rp.get('weight'):
                vals['weight'] = rp['weight']

            if rp.get('volume'):
                vals['volume'] = rp['volume']

            if rp.get('image_1920'):
                vals['image_1920'] = rp['image_1920']

            if rp.get('avg_rating'):
                vals['avg_rating'] = rp['avg_rating']

            if rp.get('top') is not None:
                vals['top'] = rp['top']

            if rp.get('price_after_discount'):
                vals['price_after_discount'] = rp['price_after_discount']

            if rp.get('ar_name'):
                vals['ar_name'] = rp['ar_name']

            if rp.get('ar_description'):
                vals['ar_description'] = rp['ar_description']

            remote_categ_ids = rp.get('pos_categ_ids') or []
            if not remote_categ_ids and rp.get('pos_categ_id'):
                rid = rp['pos_categ_id']
                if isinstance(rid, list):
                    remote_categ_ids = [rid[0]]
                elif isinstance(rid, int) and rid:
                    remote_categ_ids = [rid]
            if remote_categ_ids:
                local_pos_categ_ids = []
                for remote_categ_id in remote_categ_ids:
                    local_cid = pos_categ_map.get(remote_categ_id)
                    if local_cid:
                        local_pos_categ_ids.append(local_cid)
                if local_pos_categ_ids:
                    vals['pos_categ_ids'] = [(6, 0, local_pos_categ_ids)]

            if rp.get('available_in_pos') is not None:
                vals['available_in_pos'] = rp['available_in_pos']

            if rp.get('taxes_id'):
                local_tax_ids = self._resolve_taxes(rp['taxes_id'], uid, models_proxy)
                if local_tax_ids:
                    vals['taxes_id'] = [(6, 0, local_tax_ids)]

            if rp.get('supplier_taxes_id'):
                local_stax_ids = self._resolve_taxes(rp['supplier_taxes_id'], uid, models_proxy)
                if local_stax_ids:
                    vals['supplier_taxes_id'] = [(6, 0, local_stax_ids)]

            if existing:
                update_vals = {k: v for k, v in vals.items() if k not in ('type', 'uom_id', 'uom_po_id', 'categ_id')}
                try:
                    existing.write(update_vals)
                except Exception as e:
                    self._append_log('Warning updating product %s: %s' % (product_name, str(e)))
                product_map[remote_id] = existing.id
                self._create_migration_line('product.product', remote_id, existing.id, product_name, 'updated')
                self._append_log('Updated product: %s' % product_name)
            else:
                new_product = self.env['product.product'].create(vals)
                product_map[remote_id] = new_product.id
                self._create_migration_line('product.product', remote_id, new_product.id, product_name, 'created')
                self._append_log('Created product: %s' % product_name)

    def _has_field(self, model, field_name):
        return field_name in self.env[model]._fields

    def _migrate_price_plans(self, uid, models_proxy, product_map):
        self._append_log('--- Migrating Price Plans ---')

        plan_fields = [
            'service_id', 'department_id', 'branch_id', 'currency_id',
            'service_slot_inside', 'service_slot_outside',
            'service_price_inside', 'service_price_outside',
        ]
        if self._has_field('appointment.service.price.plan', 'location_type'):
            plan_fields.append('location_type')

        remote_plan_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'appointment.service.price.plan', 'search',
            [[]]
        )
        remote_plans = []
        for i in range(0, len(remote_plan_ids), 100):
            batch = models_proxy.execute_kw(
                self.database, uid, self.password,
                'appointment.service.price.plan', 'read',
                [remote_plan_ids[i:i + 100]],
                {'fields': plan_fields}
            )
            remote_plans.extend(batch)

        self._append_log('Found %d price plans to migrate.' % len(remote_plans))

        for rplan in remote_plans:
            service_remote_id = rplan.get('service_id') and rplan['service_id'][0]
            local_service_id = product_map.get(service_remote_id)
            if not local_service_id:
                self._append_log('Skipping price plan %d: service not found.' % rplan['id'])
                continue

            department_id = self._resolve_department(rplan.get('department_id'), uid, models_proxy)
            branch_id = self._resolve_company(rplan.get('branch_id'), uid, models_proxy)
            currency_id = self._resolve_currency(rplan.get('currency_id'), uid, models_proxy)

            domain = [
                ('service_id', '=', local_service_id),
                ('department_id', '=', department_id),
                ('branch_id', '=', branch_id),
            ]
            existing = self.env['appointment.service.price.plan'].search(domain, limit=1)

            vals = {
                'service_id': local_service_id,
                'department_id': department_id,
                'branch_id': branch_id,
                'currency_id': currency_id,
                'service_slot_inside': rplan.get('service_slot_inside', 0),
                'service_slot_outside': rplan.get('service_slot_outside', 0),
                'service_price_inside': rplan.get('service_price_inside', 0.0),
                'service_price_outside': rplan.get('service_price_outside', 0.0),
            }
            if self._has_field('appointment.service.price.plan', 'location_type') and rplan.get('location_type'):
                vals['location_type'] = rplan['location_type']

            if existing:
                self._create_migration_line('appointment.service.price.plan', rplan['id'], existing.id, 'Plan for service %d' % local_service_id, 'skipped')
                self._append_log('Skipped price plan (already exists) for service ID %d' % local_service_id)
            else:
                new_plan = self.env['appointment.service.price.plan'].create(vals)
                self._create_migration_line('appointment.service.price.plan', rplan['id'], new_plan.id, 'Plan for service %d' % local_service_id, 'created')
                self._append_log('Created price plan for service ID %d' % local_service_id)

    def _migrate_package_lines(self, uid, models_proxy, product_map):
        self._append_log('--- Migrating Package Lines ---')

        line_fields = [
            'product_id', 'product_pack_id', 'department_id', 'branch_id', 'currency_id',
            'service_slot_inside', 'service_slot_outside',
            'service_price_inside', 'service_price_outside',
        ]
        if self._has_field('appointment.package.line', 'location_type'):
            line_fields.append('location_type')

        remote_line_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'appointment.package.line', 'search',
            [[]]
        )
        remote_lines = []
        for i in range(0, len(remote_line_ids), 100):
            batch = models_proxy.execute_kw(
                self.database, uid, self.password,
                'appointment.package.line', 'read',
                [remote_line_ids[i:i + 100]],
                {'fields': line_fields}
            )
            remote_lines.extend(batch)

        self._append_log('Found %d package lines to migrate.' % len(remote_lines))

        for rline in remote_lines:
            product_remote_id = rline.get('product_id') and rline['product_id'][0]
            pack_remote_id = rline.get('product_pack_id') and rline['product_pack_id'][0]

            local_product_id = product_map.get(product_remote_id)
            local_pack_id = product_map.get(pack_remote_id)

            if not local_product_id:
                self._append_log('Skipping package line %d: product not found.' % rline['id'])
                continue

            department_id = self._resolve_department(rline.get('department_id'), uid, models_proxy)
            branch_id = self._resolve_company(rline.get('branch_id'), uid, models_proxy)
            currency_id = self._resolve_currency(rline.get('currency_id'), uid, models_proxy)

            domain = [
                ('product_id', '=', local_product_id),
                ('product_pack_id', '=', local_pack_id or False),
                ('department_id', '=', department_id),
                ('branch_id', '=', branch_id),
            ]
            existing = self.env['appointment.package.line'].search(domain, limit=1)

            vals = {
                'product_id': local_product_id,
                'product_pack_id': local_pack_id or False,
                'department_id': department_id,
                'branch_id': branch_id,
                'currency_id': currency_id,
                'service_slot_inside': rline.get('service_slot_inside', 0),
                'service_slot_outside': rline.get('service_slot_outside', 0),
                'service_price_inside': rline.get('service_price_inside', 0.0),
                'service_price_outside': rline.get('service_price_outside', 0.0),
            }
            if self._has_field('appointment.package.line', 'location_type') and rline.get('location_type'):
                vals['location_type'] = rline['location_type']

            if existing:
                self._create_migration_line('appointment.package.line', rline['id'], existing.id, 'Package line %d' % local_product_id, 'skipped')
                self._append_log('Skipped package line (already exists) for product ID %d' % local_product_id)
            else:
                new_line = self.env['appointment.package.line'].create(vals)
                self._create_migration_line('appointment.package.line', rline['id'], new_line.id, 'Package line %d' % local_product_id, 'created')
                self._append_log('Created package line for product ID %d' % local_product_id)

    def _migrate_product_components(self, uid, models_proxy, product_map):
        self._append_log('--- Migrating Product Components ---')

        comp_fields = ['component_id', 'quantity', 'product_id']

        remote_comp_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'product.component', 'search',
            [[]]
        )
        remote_components = []
        for i in range(0, len(remote_comp_ids), 100):
            batch = models_proxy.execute_kw(
                self.database, uid, self.password,
                'product.component', 'read',
                [remote_comp_ids[i:i + 100]],
                {'fields': comp_fields}
            )
            remote_components.extend(batch)

        self._append_log('Found %d product components to migrate.' % len(remote_components))

        for rcomp in remote_components:
            product_remote_id = rcomp.get('product_id') and rcomp['product_id'][0]
            component_remote_id = rcomp.get('component_id') and rcomp['component_id'][0]

            local_product_id = product_map.get(product_remote_id)
            local_component_id = product_map.get(component_remote_id)

            if not local_product_id:
                self._append_log('Skipping component %d: parent product not found.' % rcomp['id'])
                continue

            if not local_component_id:
                if component_remote_id:
                    comp_data = models_proxy.execute_kw(
                        self.database, uid, self.password,
                        'product.product', 'read', [component_remote_id],
                        {'fields': ['name', 'default_code', 'list_price', 'type']}
                    )
                    if comp_data:
                        comp_name = comp_data[0].get('name')
                        local_comp = self.env['product.product'].search([('name', '=', comp_name)], limit=1)
                        if not local_comp:
                            local_comp = self.env['product.product'].create({
                                'name': comp_name,
                                'default_code': comp_data[0].get('default_code') or False,
                                'list_price': comp_data[0].get('list_price', 0.0),
                                'type': comp_data[0].get('type', 'consu'),
                            })
                            self._append_log('Created component product: %s' % comp_name)
                        local_component_id = local_comp.id
                        product_map[component_remote_id] = local_component_id

            if not local_component_id:
                self._append_log('Skipping component %d: component product not found.' % rcomp['id'])
                continue

            domain = [
                ('product_id', '=', local_product_id),
                ('component_id', '=', local_component_id),
            ]
            existing = self.env['product.component'].search(domain, limit=1)

            vals = {
                'product_id': local_product_id,
                'component_id': local_component_id,
                'quantity': rcomp.get('quantity', 0.0),
            }

            if existing:
                self._create_migration_line('product.component', rcomp['id'], existing.id, 'Component %d' % local_component_id, 'skipped')
                self._append_log('Skipped component (already exists) for product ID %d' % local_product_id)
            else:
                new_comp = self.env['product.component'].create(vals)
                self._create_migration_line('product.component', rcomp['id'], new_comp.id, 'Component %d' % local_component_id, 'created')
                self._append_log('Created component for product ID %d' % local_product_id)

    def _create_migration_line(self, model, remote_id, local_id, name, action):
        self.env['salon.migration.line'].create({
            'migration_id': self.id,
            'model': model,
            'remote_id': remote_id,
            'local_id': local_id,
            'name': name,
            'action': action,
        })


class SalonMigrationLine(models.Model):
    _name = 'salon.migration.line'
    _description = 'Salon Migration Line'

    migration_id = fields.Many2one('salon.migration', string='Migration', ondelete='cascade')
    model = fields.Char(string='Model')
    remote_id = fields.Integer(string='Remote ID')
    local_id = fields.Integer(string='Local ID')
    name = fields.Char(string='Record Name')
    action = fields.Selection([
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('skipped', 'Skipped'),
    ], string='Action')
