// Toast 自动关闭
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toast').forEach(el => {
    const toast = new bootstrap.Toast(el, { delay: 4000 });
    toast.show();
  });

  // 数字输入框：已用空间不超过总量
  const totalInput = document.querySelector('input[name="total_space_gb"]');
  const usedInput  = document.querySelector('input[name="used_space_gb"]');

  if (totalInput && usedInput) {
    usedInput.addEventListener('change', () => {
      const total = parseFloat(totalInput.value) || 0;
      const used  = parseFloat(usedInput.value)  || 0;
      if (used > total && total > 0) {
        usedInput.setCustomValidity(
          document.documentElement.lang === 'en'
            ? `Used space cannot exceed total capacity ${total} GB`
            : `已用空间不能超过总容量 ${total} GB`
        );
        usedInput.reportValidity();
      } else {
        usedInput.setCustomValidity('');
      }
    });
  }

  // 确认删除
  document.querySelectorAll('[data-confirm]').forEach(btn => {
    btn.addEventListener('click', e => {
      if (!confirm(btn.dataset.confirm)) e.preventDefault();
    });
  });
});
