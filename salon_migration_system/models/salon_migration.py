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
        ('fetched', 'Data Fetched'),
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

    def _has_field(self, model, field_name):
        return field_name in self.env[model]._fields

    def _batch_read(self, uid, models_proxy, model, ids, fields_list, batch_size=50):
        results = []
        for i in range(0, len(ids), batch_size):
            batch = models_proxy.execute_kw(
                self.database, uid, self.password,
                model, 'read',
                [ids[i:i + batch_size]],
                {'fields': fields_list}
            )
            results.extend(batch)
        return results

    def _fetch_all_remote_data(self, uid, models_proxy):
        remote_data = {}

        self._append_log('--- Fetching all remote data ---')

        self._append_log('Fetching products...')
        product_fields = [
            'name', 'sale_ok', 'purchase_ok', 'is_appointment_package',
            'is_appointment_service', 'detailed_type', 'type', 'lst_price',
            'taxes_id', 'supplier_taxes_id', 'standard_price', 'list_price',
            'barcode', 'default_code', 'categ_id', 'pos_categ_ids',
            'available_in_pos', 'plan_ids', 'appointment_package_line_ids',
            'product_component_ids',
        ]
        product_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'product.product', 'search',
            [['&', ('detailed_type', '=', 'service'),
              '|',
              ('is_appointment_package', '=', True),
              ('is_appointment_service', '=', True)]]
        )
        remote_data['products'] = self._batch_read(uid, models_proxy, 'product.product', product_ids, product_fields) if product_ids else []
        self._append_log('Fetched %d products.' % len(remote_data['products']))

        all_categ_ids = set()
        all_pos_categ_ids = set()
        all_tax_ids = set()
        for rp in remote_data['products']:
            if rp.get('categ_id'):
                all_categ_ids.add(rp['categ_id'][0])
            for pc_id in (rp.get('pos_categ_ids') or []):
                all_pos_categ_ids.add(pc_id)
            for t_id in (rp.get('taxes_id') or []):
                all_tax_ids.add(t_id)
            for t_id in (rp.get('supplier_taxes_id') or []):
                all_tax_ids.add(t_id)

        self._append_log('Fetching product categories...')
        if all_categ_ids:
            remote_data['product_categories'] = self._batch_read(
                uid, models_proxy, 'product.category', list(all_categ_ids), ['name']
            )
        else:
            remote_data['product_categories'] = []
        self._append_log('Fetched %d product categories.' % len(remote_data['product_categories']))

        self._append_log('Fetching POS categories...')
        if all_pos_categ_ids:
            remote_data['pos_categories'] = self._batch_read(
                uid, models_proxy, 'pos.category', list(all_pos_categ_ids), ['name']
            )
        else:
            remote_data['pos_categories'] = []
        self._append_log('Fetched %d POS categories.' % len(remote_data['pos_categories']))

        self._append_log('Fetching taxes...')
        if all_tax_ids:
            remote_data['taxes'] = self._batch_read(
                uid, models_proxy, 'account.tax', list(all_tax_ids), ['name', 'type_tax_use', 'amount']
            )
        else:
            remote_data['taxes'] = []
        self._append_log('Fetched %d taxes.' % len(remote_data['taxes']))

        self._append_log('Fetching price plans...')
        plan_fields = [
            'service_id', 'department_id', 'branch_id', 'currency_id',
            'service_slot_inside', 'service_slot_outside',
            'service_price_inside', 'service_price_outside',
        ]
        if self._has_field('appointment.service.price.plan', 'location_type'):
            plan_fields.append('location_type')
        plan_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'appointment.service.price.plan', 'search', [[]]
        )
        remote_data['price_plans'] = self._batch_read(uid, models_proxy, 'appointment.service.price.plan', plan_ids, plan_fields) if plan_ids else []
        self._append_log('Fetched %d price plans.' % len(remote_data['price_plans']))

        self._append_log('Fetching package lines...')
        line_fields = [
            'product_id', 'product_pack_id', 'department_id', 'branch_id', 'currency_id',
            'service_slot_inside', 'service_slot_outside',
            'service_price_inside', 'service_price_outside',
        ]
        if self._has_field('appointment.package.line', 'location_type'):
            line_fields.append('location_type')
        line_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'appointment.package.line', 'search', [[]]
        )
        remote_data['package_lines'] = self._batch_read(uid, models_proxy, 'appointment.package.line', line_ids, line_fields) if line_ids else []
        self._append_log('Fetched %d package lines.' % len(remote_data['package_lines']))

        self._append_log('Fetching product components...')
        comp_ids = models_proxy.execute_kw(
            self.database, uid, self.password,
            'product.component', 'search', [[]]
        )
        remote_data['components'] = self._batch_read(uid, models_proxy, 'product.component', comp_ids, ['component_id', 'quantity', 'product_id']) if comp_ids else []
        self._append_log('Fetched %d product components.' % len(remote_data['components']))

        all_dept_ids = set()
        all_branch_ids = set()
        all_currency_ids = set()
        for rplan in remote_data['price_plans']:
            if rplan.get('department_id'):
                all_dept_ids.add(rplan['department_id'][0])
            if rplan.get('branch_id'):
                all_branch_ids.add(rplan['branch_id'][0])
            if rplan.get('currency_id'):
                all_currency_ids.add(rplan['currency_id'][0])
        for rline in remote_data['package_lines']:
            if rline.get('department_id'):
                all_dept_ids.add(rline['department_id'][0])
            if rline.get('branch_id'):
                all_branch_ids.add(rline['branch_id'][0])
            if rline.get('currency_id'):
                all_currency_ids.add(rline['currency_id'][0])

        self._append_log('Fetching departments...')
        if all_dept_ids:
            remote_data['departments'] = self._batch_read(
                uid, models_proxy, 'hr.department', list(all_dept_ids), ['name']
            )
        else:
            remote_data['departments'] = []
        self._append_log('Fetched %d departments.' % len(remote_data['departments']))

        self._append_log('Fetching companies/branches...')
        if all_branch_ids:
            remote_data['companies'] = self._batch_read(
                uid, models_proxy, 'res.company', list(all_branch_ids), ['name']
            )
        else:
            remote_data['companies'] = []
        self._append_log('Fetched %d companies.' % len(remote_data['companies']))

        self._append_log('Fetching currencies...')
        if all_currency_ids:
            remote_data['currencies'] = self._batch_read(
                uid, models_proxy, 'res.currency', list(all_currency_ids), ['name']
            )
        else:
            remote_data['currencies'] = []
        self._append_log('Fetched %d currencies.' % len(remote_data['currencies']))

        comp_product_ids = set()
        for rc in remote_data['components']:
            if rc.get('component_id'):
                comp_product_ids.add(rc['component_id'][0])
        existing_product_remote_ids = {rp['id'] for rp in remote_data['products']}
        missing_comp_ids = comp_product_ids - existing_product_remote_ids
        if missing_comp_ids:
            self._append_log('Fetching %d missing component products...' % len(missing_comp_ids))
            remote_data['component_products'] = self._batch_read(
                uid, models_proxy, 'product.product', list(missing_comp_ids),
                ['name', 'default_code', 'list_price', 'type']
            )
        else:
            remote_data['component_products'] = []

        self._append_log('--- All remote data fetched successfully ---')
        return remote_data

    def _build_cache(self, remote_data):
        cache = {}
        cache['categ_by_id'] = {rc['id']: rc['name'] for rc in remote_data.get('product_categories', [])}
        cache['pos_categ_by_id'] = {rc['id']: rc['name'] for rc in remote_data.get('pos_categories', [])}
        cache['tax_by_id'] = {rt['id']: rt for rt in remote_data.get('taxes', [])}
        cache['dept_by_id'] = {rd['id']: rd['name'] for rd in remote_data.get('departments', [])}
        cache['company_by_id'] = {rc['id']: rc['name'] for rc in remote_data.get('companies', [])}
        cache['currency_by_id'] = {rc['id']: rc['name'] for rc in remote_data.get('currencies', [])}
        cache['comp_product_by_id'] = {rp['id']: rp for rp in remote_data.get('component_products', [])}
        return cache

    def _resolve_categ_local(self, remote_id, cache):
        if not remote_id:
            return self.env.ref('product.product_category_all').id
        remote_name = cache['categ_by_id'].get(remote_id[0] if isinstance(remote_id, (list, tuple)) else remote_id)
        if not remote_name:
            return self.env.ref('product.product_category_all').id
        local = self.env['product.category'].search([('name', '=', remote_name)], limit=1)
        if not local:
            local = self.env['product.category'].create({'name': remote_name})
            self._append_log('Created product category: %s' % remote_name)
        return local.id

    def _resolve_pos_categ_local(self, remote_ids, cache):
        if not remote_ids:
            return []
        local_ids = []
        for rid in remote_ids:
            remote_name = cache['pos_categ_by_id'].get(rid)
            if not remote_name:
                continue
            local = self.env['pos.category'].search([('name', '=', remote_name)], limit=1)
            if not local:
                local = self.env['pos.category'].create({'name': remote_name})
                self._append_log('Created POS category: %s' % remote_name)
            local_ids.append(local.id)
        return local_ids

    def _resolve_taxes_local(self, remote_ids, cache):
        if not remote_ids:
            return []
        local_ids = []
        for rid in remote_ids:
            tax_data = cache['tax_by_id'].get(rid)
            if not tax_data:
                continue
            local = self.env['account.tax'].search([
                ('name', '=', tax_data['name']),
                ('type_tax_use', '=', tax_data.get('type_tax_use', 'sale')),
            ], limit=1)
            if local:
                local_ids.append(local.id)
        return local_ids

    def _resolve_department_local(self, remote_id, cache):
        if not remote_id:
            return False
        rid = remote_id[0] if isinstance(remote_id, (list, tuple)) else remote_id
        remote_name = cache['dept_by_id'].get(rid)
        if not remote_name:
            return False
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

    def _resolve_company_local(self, remote_id, cache):
        if not remote_id:
            return self.env.company.id
        rid = remote_id[0] if isinstance(remote_id, (list, tuple)) else remote_id
        remote_name = cache['company_by_id'].get(rid)
        if not remote_name:
            return self.env.company.id
        local = self.env['res.company'].search([('name', '=', remote_name)], limit=1)
        if not local:
            local = self.env['res.company'].create({'name': remote_name})
            self._append_log('Created company: %s' % remote_name)
        return local.id

    def _resolve_currency_local(self, remote_id, cache):
        if not remote_id:
            return self.env.company.currency_id.id
        rid = remote_id[0] if isinstance(remote_id, (list, tuple)) else remote_id
        remote_name = cache['currency_by_id'].get(rid)
        if not remote_name:
            return self.env.company.currency_id.id
        local = self.env['res.currency'].search([('name', '=', remote_name)], limit=1)
        if local:
            return local.id
        return self.env.company.currency_id.id

    def _find_existing_product(self, default_code, barcode, name):
        if default_code:
            existing = self.env['product.product'].search([('default_code', '=', default_code)], limit=1)
            if existing:
                return existing
        if barcode:
            existing = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)
            if existing:
                return existing
        if name:
            existing = self.env['product.product'].search([('name', '=', name)], limit=1)
            if existing:
                return existing
        return False

    def _get_unique_barcode(self, barcode):
        if not barcode:
            return False
        existing = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)
        if existing:
            return False
        return barcode

    def action_migrate(self):
        self.ensure_one()
        self.write({'log': '', 'state': 'draft'})
        self.migration_line_ids.unlink()

        try:
            uid, models_proxy = self._get_xmlrpc_connection()
            self.write({'state': 'connected'})
            self._append_log('Connected to %s' % self.url)

            remote_data = self._fetch_all_remote_data(uid, models_proxy)
            self.write({'state': 'fetched'})
            self._append_log('All data fetched. Processing locally...')

            cache = self._build_cache(remote_data)
            product_map = {}

            self._process_products(remote_data, cache, product_map)
            self._process_price_plans(remote_data, cache, product_map)
            self._process_package_lines(remote_data, cache, product_map)
            self._process_product_components(remote_data, cache, product_map)

            self.write({'state': 'done'})
            self._append_log('Migration completed successfully.')

        except Exception as e:
            self.write({'state': 'failed'})
            self._append_log('Migration failed: %s' % str(e))
            raise UserError(_('Migration failed: %s') % str(e))

    def _process_products(self, remote_data, cache, product_map):
        self._append_log('--- Processing Products ---')

        for rp in remote_data.get('products', []):
            remote_id = rp['id']
            product_name = rp.get('name', '')
            default_code = rp.get('default_code') or False
            barcode = rp.get('barcode') or False

            categ_id = self._resolve_categ_local(rp.get('categ_id'), cache)
            if not categ_id:
                self._append_log('Skipping product %s: mandatory categ_id not resolved.' % product_name)
                continue

            local_pos_categ_ids = self._resolve_pos_categ_local(rp.get('pos_categ_ids') or [], cache)
            local_tax_ids = self._resolve_taxes_local(rp.get('taxes_id') or [], cache)
            local_stax_ids = self._resolve_taxes_local(rp.get('supplier_taxes_id') or [], cache)

            vals = {
                'name': product_name,
                'sale_ok': rp.get('sale_ok', True),
                'purchase_ok': rp.get('purchase_ok', False),
                'is_appointment_package': rp.get('is_appointment_package', False),
                'is_appointment_service': rp.get('is_appointment_service', False),
                'detailed_type': rp.get('detailed_type', 'service'),
                'type': rp.get('type', 'service'),
                'lst_price': rp.get('lst_price', 0.0),
                'standard_price': rp.get('standard_price', 0.0),
                'list_price': rp.get('list_price', 0.0),
                'barcode': self._get_unique_barcode(barcode),
                'default_code': default_code,
                'categ_id': categ_id,
                'available_in_pos': rp.get('available_in_pos', False),
            }

            if local_pos_categ_ids:
                vals['pos_categ_ids'] = [(6, 0, local_pos_categ_ids)]

            if local_tax_ids:
                vals['taxes_id'] = [(6, 0, local_tax_ids)]

            if local_stax_ids:
                vals['supplier_taxes_id'] = [(6, 0, local_stax_ids)]

            existing = self._find_existing_product(default_code, barcode, product_name)
            if existing:
                update_vals = {k: v for k, v in vals.items() if k not in ('type', 'detailed_type')}
                try:
                    existing.write(update_vals)
                except Exception as e:
                    self._append_log('Warning updating product %s: %s' % (product_name, str(e)))
                product_map[remote_id] = existing.id
                self._create_migration_line('product.product', remote_id, existing.id, product_name, 'updated')
                self._append_log('Updated product: %s' % product_name)
            else:
                try:
                    new_product = self.env['product.product'].create(vals)
                    product_map[remote_id] = new_product.id
                    self._create_migration_line('product.product', remote_id, new_product.id, product_name, 'created')
                    self._append_log('Created product: %s' % product_name)
                except Exception as e:
                    self._append_log('Error creating product %s: %s' % (product_name, str(e)))

    def _process_price_plans(self, remote_data, cache, product_map):
        self._append_log('--- Processing Price Plans ---')

        for rplan in remote_data.get('price_plans', []):
            service_remote_id = rplan.get('service_id') and rplan['service_id'][0]
            local_service_id = product_map.get(service_remote_id)
            if not local_service_id:
                self._append_log('Skipping price plan %d: service not found.' % rplan['id'])
                continue

            department_id = self._resolve_department_local(rplan.get('department_id'), cache)
            branch_id = self._resolve_company_local(rplan.get('branch_id'), cache)
            currency_id = self._resolve_currency_local(rplan.get('currency_id'), cache)

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

    def _process_package_lines(self, remote_data, cache, product_map):
        self._append_log('--- Processing Package Lines ---')

        for rline in remote_data.get('package_lines', []):
            product_remote_id = rline.get('product_id') and rline['product_id'][0]
            pack_remote_id = rline.get('product_pack_id') and rline['product_pack_id'][0]

            local_product_id = product_map.get(product_remote_id)
            local_pack_id = product_map.get(pack_remote_id)

            if not local_product_id:
                self._append_log('Skipping package line %d: product not found.' % rline['id'])
                continue

            department_id = self._resolve_department_local(rline.get('department_id'), cache)
            branch_id = self._resolve_company_local(rline.get('branch_id'), cache)
            currency_id = self._resolve_currency_local(rline.get('currency_id'), cache)

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

    def _process_product_components(self, remote_data, cache, product_map):
        self._append_log('--- Processing Product Components ---')

        for rcomp in remote_data.get('components', []):
            product_remote_id = rcomp.get('product_id') and rcomp['product_id'][0]
            component_remote_id = rcomp.get('component_id') and rcomp['component_id'][0]

            local_product_id = product_map.get(product_remote_id)
            local_component_id = product_map.get(component_remote_id)

            if not local_product_id:
                self._append_log('Skipping component %d: parent product not found.' % rcomp['id'])
                continue

            if not local_component_id:
                if component_remote_id:
                    comp_data = cache['comp_product_by_id'].get(component_remote_id)
                    if comp_data:
                        comp_name = comp_data.get('name')
                        local_comp = self.env['product.product'].search([('name', '=', comp_name)], limit=1)
                        if not local_comp:
                            local_comp = self.env['product.product'].create({
                                'name': comp_name,
                                'default_code': comp_data.get('default_code') or False,
                                'list_price': comp_data.get('list_price', 0.0),
                                'type': comp_data.get('type', 'consu'),
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
