(function() {
  function loadEntries() {
    fetch('/api/guestbook')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var el = document.getElementById('wc-gb-entries');
        if (!data.entries || data.entries.length === 0) {
          el.innerHTML = '<em style="color:#666;">No entries yet. Be the first!</em>';
          return;
        }
        var html = '';
        for (var i = data.entries.length - 1; i >= 0; i--) {
          var e = data.entries[i];
          html += '<div style="border-bottom:1px dashed #333366; padding:6px 0;">' +
            '<strong style="color:#ff9900;">' + e.name + '</strong> ' +
            '<span style="float:right; font-size:0.75em; color:#666;">#' + e.id + '</span>' +
            '<div style="color:#ccc; margin-top:2px;">' + e.message + '</div>' +
            '</div>';
        }
        el.innerHTML = html;
      })
      .catch(function() {
        document.getElementById('wc-gb-entries').innerHTML =
          '<em style="color:#666;">Could not load guestbook.</em>';
      });
  }

  loadEntries();

  var form = document.getElementById('wc-gb-form');
  if (form) {
    form.addEventListener('submit', function(ev) {
      ev.preventDefault();
      var name = document.getElementById('wc-gb-name').value;
      var msg = document.getElementById('wc-gb-msg').value;
      var errEl = document.getElementById('wc-gb-error');
      errEl.textContent = '';

      fetch('/api/guestbook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, message: msg })
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.ok) {
          document.getElementById('wc-gb-name').value = '';
          document.getElementById('wc-gb-msg').value = '';
          loadEntries();
        } else if (data.error === 'rate_limited') {
          errEl.textContent = 'Wait ' + data.retry_after + 's before posting again.';
        } else {
          errEl.textContent = data.message || 'Error.';
        }
      })
      .catch(function() { errEl.textContent = 'Connection error.'; });
    });
  }
})();
