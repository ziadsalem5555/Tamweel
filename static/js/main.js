// CrowdFund Egypt Main JavaScript

document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss alerts after 6 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 6000);
  });

  // Reply Toggle in Comments
  const replyButtons = document.querySelectorAll('.reply-toggle-btn');
  replyButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const commentId = this.getAttribute('data-comment-id');
      const replyBox = document.getElementById('reply-box-' + commentId);
      if (replyBox) {
        if (replyBox.classList.contains('d-none')) {
          replyBox.classList.remove('d-none');
          const textarea = replyBox.querySelector('textarea');
          if (textarea) textarea.focus();
        } else {
          replyBox.classList.add('d-none');
        }
      }
    });
  });

  // Quick Donation Preset Buttons
  const presetButtons = document.querySelectorAll('.quick-donation-btn');
  const donationInput = document.getElementById('id_amount') || document.querySelector('input[name="amount"]');
  if (donationInput && presetButtons.length > 0) {
    presetButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const amount = this.getAttribute('data-amount');
        donationInput.value = amount;
        donationInput.focus();
      });
    });
  }

  // Interactive Star Rating auto-submit or visual update
  const ratingRadios = document.querySelectorAll('.rating-stars-input input[type="radio"]');
  ratingRadios.forEach(function (radio) {
    radio.addEventListener('change', function () {
      const form = this.closest('form');
      if (form) {
        form.submit();
      }
    });
  });
});
