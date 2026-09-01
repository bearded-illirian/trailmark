(function () {
  'use strict';

  // Radar custom video player — ops branding (var(--accent) purple/indigo).
  // Ported from radar-os pages.js for reuse between LRN slider and magic-link landing.
  // Public API: window.LrnPlayer.initAll(container)

  var _SVG_PLAY    = '<svg viewBox="0 0 24 24" fill="var(--accent)" width="28" height="28"><polygon points="6,4 20,12 6,20"/></svg>';
  var _SVG_PAUSE   = '<svg viewBox="0 0 24 24" fill="var(--accent)" width="28" height="28"><rect x="5" y="4" width="4" height="16"/><rect x="15" y="4" width="4" height="16"/></svg>';
  var _SVG_REPLAY  = '<svg viewBox="0 0 24 24" fill="white" width="28" height="28"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>';
  var _SVG_VOL_ON  = '<svg viewBox="0 0 24 24" fill="white" width="20" height="20"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>';
  var _SVG_VOL_OFF = '<svg viewBox="0 0 24 24" fill="white" width="20" height="20"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>';
  var _SVG_FS_ON   = '<svg viewBox="0 0 24 24" fill="white" width="20" height="20"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>';
  var _SVG_FS_OFF  = '<svg viewBox="0 0 24 24" fill="white" width="20" height="20"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>';
  var _SVG_PIP     = '<svg viewBox="0 0 24 24" fill="white" width="20" height="20"><path d="M19 7H5c-1.1 0-2 .9-2 2v9c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zm0 11h-8v-5h8v5z"/></svg>';
  var _SVG_SPEED   = '<svg viewBox="0 0 24 24" fill="white" width="20" height="20"><path d="M20.38 8.57l-1.23 1.85a8 8 0 0 1-.22 7.58H5.07A8 8 0 0 1 15.58 6.85l1.85-1.23A10 10 0 0 0 3.35 19a2 2 0 0 0 1.72 1h13.85a2 2 0 0 0 1.74-1 10 10 0 0 0-.27-10.44zm-9.79 6.84a2 2 0 0 0 2.83 0l5.66-8.49-8.49 5.66a2 2 0 0 0 0 2.83z"/></svg>';

  var _rpActive = null;

  function _rpPlayerHtml(url) {
    return '<video class="rp-video" playsinline src="' + url + '"></video>' +
      '<div class="rp-click-hint" aria-hidden="true">' + _SVG_PLAY + '</div>' +
      '<div class="rp-bar">' +
        '<div class="rp-progress-wrap"><div class="rp-progress-bar">' +
          '<div class="rp-progress-fill" style="width:0%"></div>' +
          '<div class="rp-progress-thumb" style="left:0%"></div>' +
        '</div></div>' +
        '<div class="rp-ctrl-row">' +
          '<button class="rp-btn rp-play" title="Play / Pause (Space)">' + _SVG_PLAY + '</button>' +
          '<div class="rp-vol-wrap">' +
            '<button class="rp-btn rp-vol" title="Mute (M)">' + _SVG_VOL_ON + '</button>' +
            '<input type="range" class="rp-vol-range" min="0" max="1" step="0.02" value="1">' +
          '</div>' +
          '<span class="rp-time">0:00 / 0:00</span>' +
          '<div style="flex:1"></div>' +
          '<div class="rp-speed-wrap">' +
            '<button class="rp-btn rp-speed-btn" title="Скорость">' + _SVG_SPEED + '</button>' +
            '<div class="rp-speed-menu" hidden>' +
              '<button data-rate="0.75">0.75×</button>' +
              '<button data-rate="1" class="is-active">1×</button>' +
              '<button data-rate="1.25">1.25×</button>' +
              '<button data-rate="1.5">1.5×</button>' +
              '<button data-rate="2">2×</button>' +
            '</div>' +
          '</div>' +
          '<button class="rp-btn rp-pip" title="Picture-in-Picture">' + _SVG_PIP + '</button>' +
          '<button class="rp-btn rp-fs" title="Fullscreen (F)">' + _SVG_FS_ON + '</button>' +
        '</div>' +
      '</div>';
  }

  function _rpFmt(t) {
    if (!t || isNaN(t)) return '0:00';
    var s = Math.floor(t), m = Math.floor(s / 60);
    return m + ':' + String(s % 60).padStart(2, '0');
  }

  function _rpInitAll(container) {
    container.querySelectorAll('.rp-wrap[data-rp-url]').forEach(function (wrap) {
      if (wrap.dataset.rpReady) return;
      wrap.dataset.rpReady = '1';
      _rpInit(wrap, wrap.dataset.rpUrl);
    });
  }

  function _rpInit(wrap, url) {
    var posKey = 'rp-' + btoa(url).replace(/[=+/]/g, '');
    wrap.addEventListener('mouseenter', function () { _rpActive = wrap; });
    wrap.addEventListener('click', function () { _rpLaunch(wrap, url, posKey); }, { once: true });
  }

  function _rpLaunch(wrap, url, posKey) {
    wrap.innerHTML = _rpPlayerHtml(url);
    _rpInitPlayer(wrap, url, posKey);
    wrap.querySelector('.rp-video').play().catch(function (err) { console.error('[rp] play failed:', err); });
  }

  function _rpInitPlayer(wrap, url, posKey) {
    var video     = wrap.querySelector('.rp-video');
    var fill      = wrap.querySelector('.rp-progress-fill');
    var thumb     = wrap.querySelector('.rp-progress-thumb');
    var bar       = wrap.querySelector('.rp-progress-bar');
    var timeEl    = wrap.querySelector('.rp-time');
    var playBtn   = wrap.querySelector('.rp-play');
    var volBtn    = wrap.querySelector('.rp-vol');
    var pipBtn    = wrap.querySelector('.rp-pip');
    var fsBtn     = wrap.querySelector('.rp-fs');
    var speedBtn  = wrap.querySelector('.rp-speed-btn');
    var speedMenu = wrap.querySelector('.rp-speed-menu');
    var ctrlBar   = wrap.querySelector('.rp-bar');
    var hintEl    = wrap.querySelector('.rp-click-hint');
    var volRange  = wrap.querySelector('.rp-vol-range');
    var _hintTimer;

    video.addEventListener('loadedmetadata', function () {
      var saved = parseFloat(localStorage.getItem(posKey) || '0');
      if (saved > 3 && saved < video.duration - 2) video.currentTime = saved;
      timeEl.textContent = '0:00 / ' + _rpFmt(video.duration);
    });

    var togglePlay = function () { video.paused ? video.play().catch(function (err) { console.error('[rp] play failed:', err); }) : video.pause(); };
    playBtn.addEventListener('click', togglePlay);
    video.addEventListener('click', togglePlay);
    var _ended = false;
    video.addEventListener('play', function () { playBtn.innerHTML = _SVG_PAUSE; hintEl.innerHTML = _SVG_PAUSE; _ended = false; hintEl.style.pointerEvents = ''; requestAnimationFrame(_rafLoop); });
    video.addEventListener('pause', function () { playBtn.innerHTML = _SVG_PLAY; hintEl.innerHTML = _SVG_PLAY; });
    video.addEventListener('ended', function () {
      playBtn.innerHTML = _SVG_PLAY;
      _ended = true;
      clearTimeout(_hintTimer);
      hintEl.innerHTML = _SVG_REPLAY;
      hintEl.classList.add('is-visible');
      hintEl.style.pointerEvents = 'auto';
    });
    hintEl.addEventListener('click', function () {
      if (!_ended) return;
      _ended = false;
      hintEl.style.pointerEvents = '';
      hintEl.classList.remove('is-visible');
      video.currentTime = 0;
      video.play().catch(function (err) { console.error('[rp] replay failed:', err); });
    });

    function _rafLoop() {
      if (!video.duration) return;
      var pct = video.currentTime / video.duration * 100;
      fill.style.width = pct + '%';
      thumb.style.left = pct + '%';
      if (!video.paused && !video.ended) requestAnimationFrame(_rafLoop);
    }

    video.addEventListener('timeupdate', function () {
      if (!video.duration) return;
      timeEl.textContent = _rpFmt(video.currentTime) + ' / ' + _rpFmt(video.duration);
      localStorage.setItem(posKey, String(video.currentTime));
    });

    function _barSeek(clientX) {
      if (!video.duration) return;
      var r = bar.getBoundingClientRect();
      video.currentTime = Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * video.duration;
      var pct = video.currentTime / video.duration * 100;
      fill.style.width = pct + '%';
      thumb.style.left = pct + '%';
    }
    bar.addEventListener('pointerdown', function (e) { bar.setPointerCapture(e.pointerId); _barSeek(e.clientX); });
    bar.addEventListener('pointermove', function (e) { if (!bar.hasPointerCapture(e.pointerId)) return; _barSeek(e.clientX); });
    bar.addEventListener('pointerup', function (e) { if (bar.hasPointerCapture(e.pointerId)) bar.releasePointerCapture(e.pointerId); });

    var _updateVol = function () {
      volBtn.innerHTML = (video.muted || video.volume === 0) ? _SVG_VOL_OFF : _SVG_VOL_ON;
      if (!video.muted) volRange.value = video.volume;
    };
    volBtn.addEventListener('click', function () { video.muted = !video.muted; _updateVol(); });
    volRange.addEventListener('input', function () { video.volume = parseFloat(volRange.value); video.muted = video.volume === 0; _updateVol(); });
    video.addEventListener('volumechange', _updateVol);

    speedBtn.addEventListener('click', function (e) { e.stopPropagation(); speedMenu.hidden = !speedMenu.hidden; });
    speedMenu.querySelectorAll('[data-rate]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        video.playbackRate = parseFloat(btn.dataset.rate);
        speedBtn.textContent = btn.dataset.rate + '×';
        speedMenu.querySelectorAll('[data-rate]').forEach(function (b) { b.classList.remove('is-active'); });
        btn.classList.add('is-active');
        speedMenu.hidden = true;
      });
    });
    document.addEventListener('click', function () { speedMenu.hidden = true; });

    if (!document.pictureInPictureEnabled) {
      pipBtn.hidden = true;
    } else {
      pipBtn.addEventListener('click', async function () {
        try {
          if (document.pictureInPictureElement) await document.exitPictureInPicture();
          else await video.requestPictureInPicture();
        } catch (_) {}
      });
    }

    fsBtn.addEventListener('click', function () {
      if (!document.fullscreenElement) wrap.requestFullscreen && wrap.requestFullscreen();
      else document.exitFullscreen && document.exitFullscreen();
    });
    var _fsHideTimer;
    function _fsShowBar() {
      ctrlBar.style.opacity = '1';
      ctrlBar.style.pointerEvents = 'auto';
      clearTimeout(_fsHideTimer);
      if (document.fullscreenElement === wrap && !video.paused)
        _fsHideTimer = setTimeout(function () { ctrlBar.style.opacity = '0'; ctrlBar.style.pointerEvents = 'none'; }, 3000);
    }
    document.addEventListener('fullscreenchange', function () {
      fsBtn.innerHTML = document.fullscreenElement === wrap ? _SVG_FS_OFF : _SVG_FS_ON;
      if (document.fullscreenElement === wrap) {
        wrap.addEventListener('mousemove', _fsShowBar);
        _fsShowBar();
      } else {
        wrap.removeEventListener('mousemove', _fsShowBar);
        clearTimeout(_fsHideTimer);
        ctrlBar.style.opacity = '';
        ctrlBar.style.pointerEvents = '';
      }
    });

    function _showHint() {
      hintEl.classList.add('is-visible');
      clearTimeout(_hintTimer);
      _hintTimer = setTimeout(function () { hintEl.classList.remove('is-visible'); }, 3000);
    }
    wrap.addEventListener('mouseenter', function () { _rpActive = wrap; _showHint(); });
    wrap.addEventListener('mousemove', function () { _showHint(); });
    wrap.addEventListener('mouseleave', function () { clearTimeout(_hintTimer); hintEl.classList.remove('is-visible'); });

    document.addEventListener('keydown', function (e) {
      if (_rpActive !== wrap) return;
      var tag = document.activeElement && document.activeElement.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.code === 'Space')      { e.preventDefault(); togglePlay(); }
      if (e.code === 'ArrowRight') { e.preventDefault(); video.currentTime = Math.min(video.duration || 0, video.currentTime + 10); }
      if (e.code === 'ArrowLeft')  { e.preventDefault(); video.currentTime = Math.max(0, video.currentTime - 10); }
      if (e.key === 'f' || e.key === 'F') { if (!document.fullscreenElement) wrap.requestFullscreen && wrap.requestFullscreen(); else document.exitFullscreen && document.exitFullscreen(); }
      if (e.key === 'm' || e.key === 'M') { video.muted = !video.muted; _updateVol(); }
    });
  }

  window.LrnPlayer = {
    initAll: _rpInitAll,
  };
})();
