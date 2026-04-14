(function(){
  'use strict';
  function setTheme(dark){
    const root = document.documentElement;
    if(dark){ root.classList.add('dark'); localStorage.setItem('theme','dark'); }
    else { root.classList.remove('dark'); localStorage.setItem('theme','light'); }
    const icon = document.getElementById('themeIcon');
    if(icon) icon.className = dark ? 'bi bi-moon-stars' : 'bi bi-sun';
  }
  function initThemeToggle(){
    document.documentElement.classList.remove('dark');
    localStorage.setItem('theme','light');
  }
  function initSearch(){
    const input = document.getElementById('globalSearch');
    if(!input) return;
    input.addEventListener('input', function(){
      const q = input.value.trim().toLowerCase();
      document.querySelectorAll('table tbody tr').forEach((row)=>{
        const text = row.textContent.replace(/\s+/g,' ').toLowerCase();
        row.style.display = q && !text.includes(q) ? 'none' : '';
      });
      document.querySelectorAll('.grid-cards .card, .parts-list .part-item, .role-cards .role-card, .accordion-item').forEach((item)=>{
        const text = item.textContent.replace(/\s+/g,' ').toLowerCase();
        item.style.display = q && !text.includes(q) ? 'none' : '';
      });
    });
  }
  function initAutoDismissAlerts(){
    document.querySelectorAll('.alert').forEach((alert)=>{
      setTimeout(()=>{ try{ bootstrap.Alert.getOrCreateInstance(alert).close(); } catch(e){} }, 4500);
    });
  }
  document.addEventListener('DOMContentLoaded', function(){
    initThemeToggle();
    initSearch();
    initAutoDismissAlerts();
  });
})();
