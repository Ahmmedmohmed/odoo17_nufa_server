# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta, datetime, time as dt_time
import pytz
import logging

_logger = logging.getLogger(__name__)


class AppointmentEmployeeSlot(models.Model):
    _name = 'appointment.employee.slot'
    _description = 'Appointment Employee Slot'

    name = fields.Char(string='Name', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)
    time = fields.Float(string='Time', required=True)
    state = fields.Selection([('draft', 'Draft'), ('wait', 'Waiting'), ('done', 'Done'), ('cancel', 'Cancelled')],
                             default='draft')

    @api.model
    def auto_reset_wait_to_draft(self):
        """دالة تعمل كل دقيقة لتنظيف السلوتات، قفل المواعيد، واكتشاف الإجازات المفاجئة"""

        # 1. جلب الوقت المحدد من الإعدادات، وإذا كان غير محدد أو فارغ يتم اعتماد 10 دقائق كافتراضي
        param_value = self.env['ir.config_parameter'].sudo().get_param('appointment_management_system.slot_wait_time',
                                                                       '10')
        try:
            wait_minutes = int(param_value) if param_value else 10
        except (ValueError, TypeError):
            wait_minutes = 10

        # 2. حساب الوقت بناءً على القيمة الديناميكية
        time_threshold = datetime.utcnow() - timedelta(minutes=wait_minutes)

        records = self.search([
            ('state', '=', 'wait'),
            ('write_date', '<=', time_threshold.strftime('%Y-%m-%d %H:%M:%S'))
        ])

        if records:
            for record in records:
                if hasattr(record, 'reserved_until') and record.reserved_until:
                    if fields.Datetime.now() <= record.reserved_until:
                        continue
                    else:
                        record.write({'state': 'draft', 'reserved_until': False, 'reserved_by': False})
                else:
                    record.write({'state': 'draft'})

        self.auto_close_past_slots()
        self.reassign_appointments_for_absent_employees()

    @api.model
    def auto_close_past_slots(self):
        """إغلاق السلوتات التي مضى وقتها مع معالجة الكسور العشرية"""
        user_tz = self.env.user.tz or 'Asia/Riyadh'
        now_local = datetime.now(pytz.timezone(user_tz))

        today = now_local.date()
        current_time_float = now_local.hour + (now_local.minute / 60.0) + 0.02

        past_days_slots = self.search([('state', 'in', ['draft', 'wait']), ('date', '<', today)])
        if past_days_slots:
            past_days_slots.write({'state': 'cancel'})

        today_past_slots = self.search(
            [('state', 'in', ['draft', 'wait']), ('date', '=', today), ('time', '<=', current_time_float)])
        if today_past_slots:
            today_past_slots.write({'state': 'cancel'})

    def action_change_state_wait(self):
        for record in self:
            record.write({'state': 'wait'})

    def action_change_state_done(self):
        for record in self:
            record.write({'state': 'done'})

    def action_change_state_cancel(self):
        for record in self:
            record.write({'state': 'cancel'})

    @api.model
    def action_create_employee_slots(self):
        """إنشاء السلوتات مع دعم خطة القسم، أو الاعتماد كلياً على جدول الموظف إذا لم توجد خطة"""
        today = fields.Date.today()
        department_ids = self.env['hr.department'].search(
            [('is_appointment_department', '=', True), ('is_times_confirmed', '=', True)])
        employee_ids = self.env['hr.employee'].search(
            [('is_appointment_employee', '=', True), ('department_id', 'in', department_ids.ids)])

        has_leave_module = 'hr.leave' in self.env
        user_tz_str = self.env.user.tz or 'Asia/Riyadh'
        user_tz = pytz.timezone(user_tz_str)

        for employee in employee_ids:
            employee_calendar = employee.resource_calendar_id
            if not employee_calendar:
                continue  # لو الموظف ملوش جدول عمل، نتخطاه لأنه مفيش مرجع لمواعيده

            time_plans = self.env['appointment.department.time.plan'].search(
                [('department_id', '=', employee.department_id.id)])

            existing_slots = self.search(
                [('employee_id', '=', employee.id), ('date', '>=', today), ('date', '<=', today + timedelta(days=35))])
            existing_slot_keys = set((slot.date, slot.time) for slot in existing_slots)

            employee_leaves = []
            if has_leave_module:
                employee_leaves = self.env['hr.leave'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ['validate', 'validate1']),
                    ('date_to', '>=', fields.Datetime.now())
                ])

            # 🚀 قلبنا اللوب: هنلف على الأيام الأول
            for day_offset in range(35):
                current_date = today + timedelta(days=day_offset)
                odoo_weekday = str(current_date.weekday())
                day_name_lower = current_date.strftime('%A').lower()

                # فلترة ساعات عمل الموظف في هذا اليوم مع استبعاد فترات الراحة (Lunch/Break)
                day_attendances = employee_calendar.attendance_ids.filtered(
                    lambda a: str(a.dayofweek) == odoo_weekday and getattr(a, 'day_period', '') != 'lunch'
                )

                if not day_attendances:
                    continue  # الموظف لا يعمل في هذا اليوم (إجازة أسبوعية)

                valid_time_ranges = []

                # 💡 التعديل الجوهري: تحديد مصدر الوقت (القسم أم الموظف)
                if time_plans:
                    day_plans = time_plans.filtered(lambda p: p.day == day_name_lower)
                    for plan in day_plans:
                        plan_start = plan.start_hour * 60 + plan.start_minute
                        plan_end = plan.end_hour * 60 + plan.end_minute
                        valid_time_ranges.append((plan_start, plan_end))
                else:
                    # لا توجد خطة للقسم -> نعتمد كلياً على فترات عمل الموظف (Work Schedule)
                    for att in day_attendances:
                        att_start_mins = int(round(att.hour_from * 60))
                        att_end_mins = int(round(att.hour_to * 60))
                        valid_time_ranges.append((att_start_mins, att_end_mins))

                # إنشاء السلوتات بناءً على الفترات المستخرجة
                for range_start, range_end in valid_time_ranges:
                    current_slot_start = range_start

                    while current_slot_start + 30 <= range_end:
                        slot_hour = int(current_slot_start // 60)
                        slot_minute = int(current_slot_start % 60)
                        time_float = slot_hour + (slot_minute / 60.0)
                        slot_end_mins = current_slot_start + 30

                        # التأكد النهائي أن السلوت يقع داخل أوقات عمل الموظف الفعيلة ولا يتقاطع مع الراحة
                        is_inside_employee_hours = False
                        for att in day_attendances:
                            att_start_mins = int(round(att.hour_from * 60))
                            att_end_mins = int(round(att.hour_to * 60))
                            if att_start_mins <= current_slot_start and slot_end_mins <= att_end_mins:
                                is_inside_employee_hours = True
                                break

                        if not is_inside_employee_hours:
                            current_slot_start += 30
                            continue

                        # التحقق من الإجازات الرسمية (Leaves)
                        is_on_leave = False
                        if employee_leaves:
                            local_dt = user_tz.localize(
                                datetime.combine(current_date, dt_time(hour=slot_hour, minute=slot_minute)))
                            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                            slot_end_utc = utc_dt + timedelta(minutes=30)

                            for l in employee_leaves:
                                if l.request_date_from <= current_date <= l.request_date_to:
                                    is_partial = False
                                    if hasattr(l, 'request_unit_hours') and l.request_unit_hours:
                                        is_partial = True
                                    elif hasattr(l, 'request_unit_half') and l.request_unit_half:
                                        is_partial = True

                                    if not is_partial:
                                        is_on_leave = True
                                        break
                                    else:
                                        if l.date_from and l.date_to:
                                            if utc_dt < l.date_to and slot_end_utc > l.date_from:
                                                is_on_leave = True
                                                break

                        if is_on_leave:
                            current_slot_start += 30
                            continue

                        # إنشاء السلوت إذا لم يكن موجوداً
                        if (current_date, time_float) not in existing_slot_keys:
                            self.create({
                                'name': f'{slot_hour:02d}:{slot_minute:02d}',
                                'employee_id': employee.id,
                                'date': current_date,
                                'time': time_float,
                                'state': 'draft'
                            })
                            existing_slot_keys.add((current_date, time_float))

                        current_slot_start += 30

        self.reassign_appointments_for_absent_employees()
    @api.model
    def reassign_appointments_for_absent_employees(self):
        if 'hr.leave' not in self.env:
            return

        today = fields.Date.today()
        try:
            leaves = self.env['hr.leave'].sudo().search([
                ('state', 'in', ['validate', 'validate1']),
                ('date_to', '>=', fields.Datetime.now())
            ])

            user_tz_str = self.env.user.tz or 'Asia/Riyadh'
            user_tz = pytz.timezone(user_tz_str)

            for leave in leaves:
                if not leave.request_date_from or not leave.request_date_to:
                    continue

                is_partial = False
                if hasattr(leave, 'request_unit_hours') and leave.request_unit_hours:
                    is_partial = True
                elif hasattr(leave, 'request_unit_half') and leave.request_unit_half:
                    is_partial = True

                empty_slots = self.sudo().search([
                    ('employee_id', '=', leave.employee_id.id),
                    ('state', '=', 'draft'),
                    ('date', '>=', leave.request_date_from),
                    ('date', '<=', leave.request_date_to)
                ])

                for slot in empty_slots:
                    if not is_partial:
                        slot.write({'state': 'cancel'})
                    else:
                        slot_hour = int(slot.time)
                        slot_minute = int(round((slot.time - slot_hour) * 60))
                        if slot_minute == 60:
                            slot_hour += 1
                            slot_minute = 0

                        local_dt = user_tz.localize(
                            datetime.combine(slot.date, dt_time(hour=slot_hour, minute=slot_minute)))
                        utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                        slot_end_utc = utc_dt + timedelta(minutes=30)

                        if utc_dt < leave.date_to and slot_end_utc > leave.date_from:
                            slot.write({'state': 'cancel'})

                if not is_partial:
                    appointments = self.env['appointment.management'].sudo().search([
                        ('employee_id', '=', leave.employee_id.id),
                        ('state', 'in', ['1', '2']),
                        ('date', '>=', datetime.combine(leave.request_date_from, dt_time.min)),
                        ('date', '<=', datetime.combine(leave.request_date_to, dt_time.max))
                    ])
                else:
                    appointments = self.env['appointment.management'].sudo().search([
                        ('employee_id', '=', leave.employee_id.id),
                        ('state', 'in', ['1', '2']),
                        ('date', '>=', leave.date_from),
                        ('date', '<', leave.date_to)
                    ])

                for appt in appointments:
                    department_id = leave.employee_id.department_id.id
                    appt_date = appt.date.date()
                    required_times = appt.slot_ids.mapped('time')
                    appt_end_date = appt.date + timedelta(minutes=len(required_times) * 30)

                    alt_employees = self.env['hr.employee'].sudo().search([
                        ('department_id', '=', department_id),
                        ('is_appointment_employee', '=', True),
                        ('id', '!=', leave.employee_id.id)
                    ])

                    for alt_emp in alt_employees:
                        alt_leave = self.env['hr.leave'].sudo().search_count([
                            ('employee_id', '=', alt_emp.id),
                            ('state', 'in', ['validate', 'validate1']),
                            ('date_from', '<', appt_end_date),
                            ('date_to', '>', appt.date)
                        ])
                        if alt_leave > 0:
                            continue

                        alt_slots = self.sudo().search([
                            ('employee_id', '=', alt_emp.id),
                            ('date', '=', appt_date),
                            ('time', 'in', required_times),
                            ('state', '=', 'draft')
                        ])

                        if len(alt_slots) == len(required_times):
                            appt.slot_ids.write({'state': 'cancel'})
                            if hasattr(appt.slot_ids, 'reserved_by'):
                                appt.slot_ids.write({'reserved_by': False, 'reserved_until': False})

                            appt.write({
                                'employee_id': alt_emp.id,
                                'slot_ids': [(6, 0, alt_slots.ids)]
                            })

                            new_state = 'wait' if appt.state == '1' else 'done'
                            vals = {'state': new_state}
                            if hasattr(alt_slots, 'reserved_by'):
                                vals['reserved_by'] = appt.id
                            alt_slots.write(vals)

                            break

        except Exception as e:
            _logger.error(f"خطأ في معالجة إجازات الموظفين: {str(e)}")
            pass