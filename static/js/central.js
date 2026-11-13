'use strict';
function setTheme(theme) { document.documentElement.dataset.theme = theme === 'bluemetal' ? 'bluemetal' : 'moonlight'; }
try { setTheme(localStorage.getItem('ls-theme')); } catch (_) { setTheme('moonlight'); }
document.getElementById('theme-toggle')?.addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'moonlight' ? 'bluemetal' : 'moonlight';
  setTheme(theme); try { localStorage.setItem('ls-theme', theme); } catch (_) { /* Armazenamento indisponível. */ }
});
document.getElementById('menu-toggle')?.addEventListener('click', (event) => {
  event.currentTarget.setAttribute('aria-expanded', String(document.body.classList.toggle('menu-open')));
});
document.querySelectorAll('aside a').forEach((link) => { if (link.pathname === location.pathname) link.classList.add('active'); });
document.querySelectorAll('[data-dialog]').forEach((button) => button.addEventListener('click', () => {
  document.getElementById(button.dataset.dialog)?.showModal();
}));
document.querySelectorAll('[data-close-dialog]').forEach((button) => button.addEventListener('click', () => {
  button.closest('dialog')?.close();
}));
const subscriptionForm = document.getElementById('new-subscription-form');
const productSelect = subscriptionForm?.querySelector('select[name="produto_id"]');
const planProduct = document.getElementById('plan-product');
if (planProduct) {
  const updateTier = () => {
    const field = document.getElementById('commercial-tier-field');
    const tier = document.getElementById('commercial-tier');
    if (!field || !tier) return;
    const commercial = planProduct.selectedOptions[0]?.dataset.code === 'COMERCIAL';
    field.hidden = !commercial; tier.disabled = !commercial; tier.required = commercial;
  };
  planProduct.addEventListener('change', updateTier); updateTier();
}
const planSelect = subscriptionForm?.querySelector('select[name="plano_id"]');
if (productSelect && planSelect) {
  const filterPlans = () => {
    const previous = planSelect.value;
    [...planSelect.options].forEach((option) => { option.hidden = option.dataset.product !== productSelect.value; option.disabled = option.hidden; });
    const available = [...planSelect.options].filter((option) => !option.disabled);
    planSelect.value = available.find((option) => option.value === previous)?.value || available[0]?.value || '';
    planSelect.disabled = available.length === 0;
    const feedback = document.getElementById('subscription-plan-feedback');
    if (feedback) feedback.hidden = available.length > 0;
    const submit = document.getElementById('create-subscription-button');
    if (submit) submit.disabled = available.length === 0 || submit.dataset.prerequisites === 'false';
  };
  productSelect.addEventListener('change', filterPlans); filterPlans();
}