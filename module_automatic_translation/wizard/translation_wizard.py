from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError
import polib, os, contextlib, io
import numpy as np

try:
    from deep_translator import GoogleTranslator
    import socket, base64, googletrans
    import googletrans
except ImportError as e:
    os.system("pip3 install deep_translator")
    os.system("pip3 install googletrans")
    os.system("pip3 install base64")

NEW_LANG_KEY = '__new__'


class TranslationWizard(models.TransientModel):
    _name = 'translation.wizard'
    _description = "Translation"

    @api.model
    def _get_languages(self):
        langs = self.env['res.lang'].get_installed()
        return [(NEW_LANG_KEY, _('New Language (Empty translation template)'))] + langs

    name = fields.Char('File Name', readonly=True)
    lang = fields.Selection(
        _get_languages,
        string='Language',
        required=True,
        default=NEW_LANG_KEY
    )
    modules = fields.Many2one(
        'ir.module.module',
        required=True,
        string='App To Translate',
        domain=[('state', '=', 'installed')]
    )

    def isConnected(self):
        try:
            sock = socket.create_connection(("www.google.com", 80))
            if sock is not None:
                sock.close()
            return True
        except OSError:
            pass
        return False

    def export_file(self):
        if self.isConnected() == True:
            this = self[0]
            path = ''
            path_str = ''
            path_list = []
            lang = this.lang if this.lang != NEW_LANG_KEY else False
            mods = sorted(this.mapped('modules.name')) or ['all']
            if lang == False:
                raise ValidationError('Please Select Language')
            path_abs = os.path.abspath(__file__).split('/')
            for i in path_abs:
                if i:
                    path_list.append(i)
                    path_str = '/'.join(path_list)
                    for (root, dirs, files) in os.walk(f'/{path_str}'):
                        for d in dirs:
                            if d == this.modules.name:
                                path = path_str
                        break
            if path == '':
                raise ValidationError('Standard Module In Not Working')
            with contextlib.closing(io.BytesIO()) as buf:
                tools.trans_export(lang, mods, buf, 'po', self._cr)
                out = base64.encodebytes(buf.getvalue())
                d = base64.b64decode(out)
            filename = 'new'
            if lang:
                filename = tools.get_iso_codes(lang)
            elif len(mods) == 1:
                filename = mods[0]
            extension = 'po'
            name = "%s.%s" % (filename, extension)
            pofile = polib.pofile(d.decode('utf-8').strip())
            language = googletrans.LANGUAGES
            lang_keys = list(language.keys())
            if this.lang.replace('_', '-').lower() in lang_keys or this.lang.split('_')[0] in lang_keys:
                for entry in np.array([e for e in pofile]):
                    if this.lang == 'zh_CN' or this.lang == 'zh_TW':
                        translated = GoogleTranslator(
                            source='english',
                            target=this.lang.replace('_', '-')
                        ).translate(entry.msgid)
                    elif this.lang == 'sr@latin':
                        translated = GoogleTranslator(
                            source='english',
                            target=this.lang[0:2]
                        ).translate(entry.msgid)
                    else:
                        translated = GoogleTranslator(
                            source='english',
                            target=this.lang.split('_')[0]
                        ).translate(entry.msgid)
                    entry.msgstr = translated
            else:
                raise ValidationError("This Language Not Supported")
            try:
                os.chmod(f'/{path}/{this.modules.name}', 0o777)
                if not os.path.isdir(f'/{path}/{this.modules.name}/i18n'):
                    os.makedirs(f'/{path}/{this.modules.name}/i18n')
            except:
                raise ValidationError("You have no permissions to create folder. Please give the permission.")
            pofile.save(f'/{path}/{this.modules.name}/i18n/{name}')
            lang_record = self.env['res.lang'].search([('code', '=', lang)])
            if not lang_record:
                raise ValidationError("Language with code '%s' not found" % lang)
            a = self.env['base.language.install'].create({'lang_ids': [(6, 0, [lang_record.id])]})
            return {
                'name': _('Language Pack'),
                'view_mode': 'form',
                'view_id': False,
                'res_model': 'base.language.install',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_id': a.id,
            }
        else:
            raise ValidationError("Please Connect Your Internet")
