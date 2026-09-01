from . import controllers
from . import models


def _post_init_hook(env):
    """
    Post-init hook to migrate existing wallet balances to loyalty cards.
    This runs after module installation/upgrade.
    """
    from odoo.addons.sms_mobile_sa_otp.data.migrate_wallet_balances import migrate_existing_wallets
    migrate_existing_wallets(env)
