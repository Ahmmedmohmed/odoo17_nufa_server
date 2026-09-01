# -*- coding: utf-8 -*-
"""
Migration script to sync existing wallet balances to loyalty cards.
Run this script after upgrading the module to populate eWallet cards
for customers with existing wallet balances.

Usage from Odoo shell:
    from odoo.addons.sms_mobile_sa_otp.data.migrate_wallet_balances import migrate_existing_wallets
    migrate_existing_wallets(env)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate_existing_wallets(env):
    """
    Migrate existing wallet balances from wallet.transaction to loyalty.card.
    This creates eWallet cards for all partners with positive wallet balance.
    """
    _logger.info("Starting wallet balance migration to loyalty cards...")

    # Get the eWallet program
    program = env.ref('sms_mobile_sa_otp.customer_ewallet_program', raise_if_not_found=False)
    if not program:
        _logger.error("eWallet program not found! Please upgrade the sms_mobile_sa_otp module first.")
        return False

    # Find all partners with wallet transactions
    env.cr.execute("""
        SELECT
            partner_id,
            COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as balance
        FROM wallet_transaction
        WHERE state = 'confirmed'
        GROUP BY partner_id
        HAVING
            COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) > 0
    """)
    results = env.cr.fetchall()

    if not results:
        _logger.info("No partners with positive wallet balance found.")
        return True

    _logger.info(f"Found {len(results)} partners with positive wallet balance to migrate.")

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    LoyaltyCard = env['loyalty.card'].sudo()
    ResPartner = env['res.partner'].sudo()

    for partner_id, balance in results:
        try:
            partner = ResPartner.browse(partner_id)
            if not partner.exists():
                _logger.warning(f"Partner ID {partner_id} not found, skipping...")
                skipped_count += 1
                continue

            # Check if partner already has an eWallet card
            if partner.ewallet_card_id:
                # Update existing card balance
                partner.ewallet_card_id.write({'points': balance})
                _logger.info(f"Updated existing eWallet card for {partner.name}: {balance}")
                migrated_count += 1
                continue

            # Check if there's already a card for this partner in the program
            existing_card = LoyaltyCard.search([
                ('program_id', '=', program.id),
                ('partner_id', '=', partner_id)
            ], limit=1)

            if existing_card:
                # Link and update existing card
                partner.write({'ewallet_card_id': existing_card.id})
                existing_card.write({'points': balance})
                _logger.info(f"Linked existing card to {partner.name}: {balance}")
            else:
                # Create new loyalty card
                card = LoyaltyCard.create({
                    'program_id': program.id,
                    'partner_id': partner_id,
                    'points': balance,
                })
                partner.write({'ewallet_card_id': card.id})
                _logger.info(f"Created new eWallet card for {partner.name}: {balance}")

            migrated_count += 1

        except Exception as e:
            _logger.error(f"Error migrating partner ID {partner_id}: {str(e)}")
            error_count += 1

    _logger.info(f"Migration completed: {migrated_count} migrated, {skipped_count} skipped, {error_count} errors")
    return True


def sync_all_wallet_balances(env):
    """
    Sync all wallet balances with their loyalty cards.
    Use this to reconcile any discrepancies.
    """
    _logger.info("Syncing all wallet balances with loyalty cards...")

    program = env.ref('sms_mobile_sa_otp.customer_ewallet_program', raise_if_not_found=False)
    if not program:
        _logger.error("eWallet program not found!")
        return False

    # Find all partners with ewallet cards
    partners = env['res.partner'].sudo().search([('ewallet_card_id', '!=', False)])

    synced_count = 0
    for partner in partners:
        try:
            wallet_balance = partner.wallet_balance
            card_balance = partner.ewallet_card_id.points

            if abs(wallet_balance - card_balance) > 0.01:  # Small tolerance for floating point
                partner.ewallet_card_id.write({'points': wallet_balance})
                _logger.info(f"Synced {partner.name}: card {card_balance} -> {wallet_balance}")
                synced_count += 1
        except Exception as e:
            _logger.error(f"Error syncing partner {partner.name}: {str(e)}")

    _logger.info(f"Sync completed: {synced_count} cards updated")
    return True
