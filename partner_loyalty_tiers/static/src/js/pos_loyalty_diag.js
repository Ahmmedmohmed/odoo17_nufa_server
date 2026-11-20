/** @odoo-module */

/**
 * أداة تشخيص محدَّثة — تفحص شكل البيانات بدقة
 * للتطوير فقط. احذفها قبل النشر.
 *
 * الاستخدام في Console:
 *   window.__loyaltyTierDiag()
 */

import { PosOrder } from "@point_of_sale/app/models/pos_order";

// نفس دوال الـ normalize من ملف الـ patch للتحقق المستقل
function normalizeManyOne(value) {
    if (!value && value !== 0) return null;
    if (Array.isArray(value))      return typeof value[0] === "number" ? value[0] : null;
    if (typeof value === "object") return typeof value.id === "number" ? value.id : null;
    if (typeof value === "number") return value;
    return null;
}
function normalizeManyMany(value) {
    if (!value || !Array.isArray(value) || value.length === 0) return [];
    const first = value[0];
    if (typeof first === "number") return value;
    if (typeof first === "object" && first !== null) return value.map(v => v.id).filter(Number.isInteger);
    return [];
}

window.__loyaltyTierDiag = function () {
    console.group("🔍 [LoyaltyTiers] Diagnostic Report");

    // ── الوصول للـ POS service ──────────────────────────────────────────────
    let pos = null;
    try {
        for (const app of Object.values(owl.__apps__ || {})) {
            if (app.env?.services?.pos) { pos = app.env.services.pos; break; }
        }
    } catch (e) {
        console.warn("تعذّر الوصول لـ POS service:", e);
    }

    if (!pos) {
        console.error("❌ POS service غير موجود. تأكد أنك داخل شاشة الـ POS.");
        console.groupEnd();
        return;
    }

    // ── 1. فحص loyalty.reward ──────────────────────────────────────────────
    console.group("📦 loyalty.reward");
    const rewards = Object.values(pos.models?.["loyalty.reward"]?.records ?? {});
    if (!rewards.length) {
        console.warn("لا توجد rewards محمّلة.");
    } else {
        rewards.forEach(r => {
            const raw = r.allowed_tier_ids;
            const normalized = normalizeManyMany(raw);
            const status = raw === undefined ? "❌ MISSING" : normalized.length ? `✅ [${normalized.join(",")}]` : "⚪ فارغ (للجميع)";
            console.log(`Reward [${r.id}] "${r.description ?? r.name}" → allowed_tier_ids raw:`, raw, "→ normalized:", status);
        });
    }
    console.groupEnd();

    // ── 2. فحص res.partner ────────────────────────────────────────────────
    console.group("👥 res.partner (أول 5)");
    const partners = Object.values(pos.models?.["res.partner"]?.records ?? {}).slice(0, 5);
    if (!partners.length) {
        console.warn("لا توجد partners محمّلة.");
    } else {
        partners.forEach(p => {
            const raw = p.loyalty_tier_id;
            const normalized = normalizeManyOne(raw);
            const status = raw === undefined ? "❌ MISSING" : normalized ? `✅ ID=${normalized}` : "⚪ null";
            console.log(`Partner [${p.id}] "${p.name}" → loyalty_tier_id raw:`, raw, "→ normalized:", status);
        });
    }
    console.groupEnd();

    // ── 3. فحص loyalty.tier ───────────────────────────────────────────────
    console.group("🏆 loyalty.tier");
    const tiers = Object.values(pos.models?.["loyalty.tier"]?.records ?? {});
    if (!tiers.length) {
        console.error(
            "❌ loyalty.tier غير موجود في POS models.\n" +
            "المشكلة في الـ Backend: _get_pos_data أو _pos_data_process\n" +
            "لم تُرسِل التايرز، أو الـ JS لم يسجّلها كـ model."
        );
    } else {
        tiers.forEach(t => console.log(`Tier [${t.id}] "${t.name}" | min: ${t.min_purchase}`));
    }
    console.groupEnd();

    // ── 4. فحص الـ patch ──────────────────────────────────────────────────
    console.group("🩹 Patch Status");
    const desc = Object.getOwnPropertyDescriptor(PosOrder.prototype, "claimableRewards");
    if (desc?.get) {
        const src = desc.get.toString();
        const isPatched = src.includes("normalizeManyMany") || src.includes("allowedIds");
        console.log(isPatched ? "✅ Patch مطبَّق بشكل صحيح." : "⚠️ Getter موجود لكن قد لا يكون الـ patch.");
    } else {
        console.error("❌ claimableRewards getter غير موجود — الـ patch لم يُطبَّق.");
    }
    console.groupEnd();

    console.groupEnd();
};

console.log("%c[LoyaltyTiers] Diag ready → window.__loyaltyTierDiag()", "color:purple;font-weight:bold");