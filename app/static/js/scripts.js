(function () {
  'use strict';

  function initSearch() {
    const input = document.getElementById('globalSearch');
    if (!input) return;

    input.addEventListener('input', function () {
      const query = input.value.trim().toLowerCase();

      document.querySelectorAll('table tbody tr').forEach((row) => {
        const text = row.textContent.replace(/\s+/g, ' ').toLowerCase();
        row.style.display = query && !text.includes(query) ? 'none' : '';
      });

      document.querySelectorAll('.grid-cards .card, .parts-list .part-item, .accordion-item').forEach((item) => {
        const text = item.textContent.replace(/\s+/g, ' ').toLowerCase();
        item.style.display = query && !text.includes(query) ? 'none' : '';
      });
    });
  }

  function initAutoDismissAlerts() {
    document.querySelectorAll('.alert').forEach((alert) => {
      setTimeout(() => {
        try {
          bootstrap.Alert.getOrCreateInstance(alert).close();
        } catch (error) {
          // Ignore bootstrap close errors for already removed alerts.
        }
      }, 4500);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSearch();
    initAutoDismissAlerts();
  });
})();
