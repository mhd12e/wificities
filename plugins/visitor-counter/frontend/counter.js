(function() {
  fetch('/api/visitors')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var totalStr = String(data.total);
      // Pad to at least 6 digits for that retro counter look
      while (totalStr.length < 6) totalStr = '0' + totalStr;

      var digits = '';
      for (var i = 0; i < totalStr.length; i++) {
        digits += '<span class="wc-vc-digit">' + totalStr[i] + '</span>';
      }

      var el = document.getElementById('wc-vc-total');
      if (el) el.innerHTML = digits;

      var onlineEl = document.getElementById('wc-vc-online');
      if (onlineEl) {
        onlineEl.textContent = data.current + ' connected right now';
      }
    })
    .catch(function() {
      var el = document.getElementById('wc-vc-total');
      if (el) el.innerHTML = '<span class="wc-vc-digit">E</span><span class="wc-vc-digit">R</span><span class="wc-vc-digit">R</span>';
    });
})();
