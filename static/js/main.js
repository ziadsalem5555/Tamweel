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

  // Modern Tamweel 5-Star Rating Component
  const starRatingContainers = document.querySelectorAll('.tamweel-star-rating');
  starRatingContainers.forEach(function (container) {
    const buttons = Array.from(container.querySelectorAll('.star-rating-btn'));
    const form = container.closest('form');
    const scoreInput = form ? form.querySelector('input[name="score"]') : null;
    const labelSpan = form ? form.querySelector('#ratingLabelSpan') : null;

    let selectedRating = parseInt(container.getAttribute('data-initial-rating'), 10) || 0;

    function renderRating(rating, isHover) {
      buttons.forEach(function (btn, idx) {
        const starVal = idx + 1;
        if (isHover) {
          if (starVal <= rating) {
            btn.classList.add('is-hovered');
          } else {
            btn.classList.remove('is-hovered');
          }
        } else {
          btn.classList.remove('is-hovered');
          if (starVal <= rating) {
            btn.classList.add('is-selected');
          } else {
            btn.classList.remove('is-selected');
          }
        }
      });
    }

    // Initial state
    renderRating(selectedRating, false);

    // Hover & Click interactions
    buttons.forEach(function (btn, idx) {
      const starVal = idx + 1;
      
      btn.addEventListener('mouseenter', function () {
        renderRating(starVal, true);
      });

      btn.addEventListener('mouseleave', function () {
        renderRating(selectedRating, false);
      });

      btn.addEventListener('click', function (e) {
        e.preventDefault();
        selectedRating = starVal;
        container.setAttribute('data-initial-rating', starVal);
        if (scoreInput) {
          scoreInput.value = starVal;
        }
        renderRating(selectedRating, false);
        if (labelSpan) {
          labelSpan.textContent = 'Your rating:';
        }
        if (form) {
          form.submit();
        }
      });
    });

    container.addEventListener('mouseleave', function () {
      renderRating(selectedRating, false);
    });
  });

  try {
    localStorage.removeItem('tamweel_theme');
  } catch (e) {}
});




