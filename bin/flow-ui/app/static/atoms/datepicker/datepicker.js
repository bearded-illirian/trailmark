/**
 * datepicker.js — Ops UI Library: DatePicker
 *
 * Lightweight custom date picker. No external dependencies.
 * Triggered by [data-datepicker] attribute on <input type="text">.
 * Outputs dates in DD.MM.YYYY format.
 *
 * Main calendar always stays in "days" mode — size never changes.
 * Month / year selection appears in a popup overlay above the calendar.
 *
 * Popup chains:
 *   [Month] click → popup months grid → pick month → popup closes
 *   [Year]  click → popup years grid  → pick year  → popup months grid → pick month → popup closes
 *
 * Public API (window.DatePicker):
 *   DatePicker.init()            — scan & init all [data-datepicker] inputs
 *   DatePicker.initElement(el)   — init a single input element
 *   DatePicker.destroy()         — remove all pickers and listeners
 */

(function () {
    "use strict";

    // ── Constants ──────────────────────────────────────────────
    var MONTHS_RU = [
        "Январь","Февраль","Март","Апрель","Май","Июнь",
        "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"
    ];
    var MONTHS_SHORT = [
        "Янв","Фев","Мар","Апр","Май","Июн",
        "Июл","Авг","Сен","Окт","Ноя","Дек"
    ];
    var WEEKDAYS = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"];

    // ── State ──────────────────────────────────────────────────
    var _active = null;  // { el, wrap, viewYear, viewMonth }
    var _popup  = null;  // { overlay, mode: "months"|"years" }
    var _bound  = [];

    // ── Helpers ────────────────────────────────────────────────
    // v2.0 (atom v1.0.0): dual-format support DD.MM.YYYY (default "ru") + YYYY-MM-DD ("iso").
    // Format read from element's data-format attribute (via _getFormat).
    function _getFormat(el) {
        return (el && el.getAttribute && el.getAttribute("data-format")) === "iso" ? "iso" : "ru";
    }

    function _parseDate(str, fmt) {
        if (!str) return null;
        var m;
        if (fmt === "iso") {
            m = String(str).match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
            if (!m) return null;
            var d = new Date(+m[1], +m[2] - 1, +m[3]);
            return isNaN(d.getTime()) ? null : d;
        }
        m = String(str).match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
        if (!m) return null;
        var d = new Date(+m[3], +m[2] - 1, +m[1]);
        return isNaN(d.getTime()) ? null : d;
    }

    function _formatDate(d, fmt) {
        var dd = String(d.getDate()).padStart(2, "0");
        var mm = String(d.getMonth() + 1).padStart(2, "0");
        var yyyy = d.getFullYear();
        if (fmt === "iso") return yyyy + "-" + mm + "-" + dd;
        return dd + "." + mm + "." + yyyy;
    }

    function _sameDay(a, b) {
        return a && b &&
            a.getFullYear() === b.getFullYear() &&
            a.getMonth()    === b.getMonth()    &&
            a.getDate()     === b.getDate();
    }

    // ── Position ───────────────────────────────────────────────
    function _position(wrap, el) {
        var rect    = el.getBoundingClientRect();
        var scrollY = window.pageYOffset || document.documentElement.scrollTop;
        var scrollX = window.pageXOffset || document.documentElement.scrollLeft;

        wrap.style.width = rect.width + "px";
        wrap.style.left  = (rect.left + scrollX) + "px";

        var wrapH = wrap.offsetHeight || 300;
        var spaceBelow = window.innerHeight - rect.bottom;

        if (spaceBelow >= wrapH + 8 || spaceBelow >= rect.top) {
            wrap.style.top  = (rect.bottom + scrollY + 4) + "px";
        } else {
            wrap.style.top  = (rect.top + scrollY - wrapH - 4) + "px";
        }
        wrap.style.bottom = "";
    }

    // ── Build: days grid ───────────────────────────────────────
    function _buildDays(year, month, selected) {
        var today       = new Date();
        var firstDay    = new Date(year, month, 1);
        var startDow    = (firstDay.getDay() + 6) % 7; // Mon=0
        var daysInMonth = new Date(year, month + 1, 0).getDate();
        var daysInPrev  = new Date(year, month, 0).getDate();

        var html = '<div class="dp-grid"><div class="dp-weekdays">';
        WEEKDAYS.forEach(function (w) {
            html += '<div class="dp-weekday">' + w + '</div>';
        });
        html += '</div><div class="dp-days">';

        var cells = [];
        for (var i = startDow - 1; i >= 0; i--) {
            cells.push({ day: daysInPrev - i, month: month - 1,
                year: month === 0 ? year - 1 : year, other: true });
        }
        for (var d = 1; d <= daysInMonth; d++) {
            cells.push({ day: d, month: month, year: year, other: false });
        }
        var rem = cells.length % 7;
        if (rem !== 0) {
            for (var d2 = 1; d2 <= 7 - rem; d2++) {
                cells.push({ day: d2, month: month + 1,
                    year: month === 11 ? year + 1 : year, other: true });
            }
        }

        cells.forEach(function (c) {
            var date = new Date(c.year, c.month, c.day);
            var cls  = "dp-day";
            if (c.other) cls += " dp-day--other-month";
            if (!c.other && _sameDay(date, today)) cls += " dp-day--today";
            if (selected && _sameDay(date, selected)) cls += " dp-day--selected";
            html += '<div class="' + cls + '" data-y="' + c.year +
                    '" data-m="' + c.month + '" data-d="' + c.day + '">' + c.day + '</div>';
        });

        html += '</div></div>';
        return html;
    }

    // ── Build: months grid ─────────────────────────────────────
    function _buildMonths(viewYear, viewMonth) {
        var curMonth = new Date().getMonth();
        var curYear  = new Date().getFullYear();

        var html = '<div class="dp-months">';
        MONTHS_SHORT.forEach(function (name, i) {
            var cls = "dp-month";
            if (i === curMonth && viewYear === curYear) cls += " dp-month--today";
            if (i === viewMonth) cls += " dp-month--selected";
            html += '<div class="' + cls + '" data-month="' + i + '">' + name + '</div>';
        });
        html += '</div>';
        return html;
    }

    // ── Build: years grid ──────────────────────────────────────
    function _buildYears(viewYear) {
        var curYear = new Date().getFullYear();
        var start   = Math.floor(viewYear / 10) * 10 - 1;
        var html    = '<div class="dp-years">';
        for (var y = start; y <= start + 11; y++) {
            var cls   = "dp-year";
            if (y === curYear)  cls += " dp-year--today";
            if (y === viewYear) cls += " dp-year--selected";
            var muted = (y === start || y === start + 11) ? " dp-year--other" : "";
            html += '<div class="' + cls + muted + '" data-year="' + y + '">' + y + '</div>';
        }
        html += '</div>';
        return html;
    }

    // ── Popup ──────────────────────────────────────────────────
    function _openPopup(mode) {
        if (!_active) return;
        if (_popup) _closePopupImmediate();

        var s        = _active;
        var wrapRect = s.wrap.getBoundingClientRect();
        var scrollY  = window.pageYOffset || document.documentElement.scrollTop;
        var scrollX  = window.pageXOffset || document.documentElement.scrollLeft;

        var overlay = document.createElement("div");
        overlay.className = "dp-popup-overlay";
        overlay.style.top    = (wrapRect.top  + scrollY) + "px";
        overlay.style.left   = (wrapRect.left + scrollX) + "px";
        overlay.style.width  = wrapRect.width + "px";
        overlay.style.height = s.wrap.offsetHeight + "px";
        document.body.appendChild(overlay);

        _popup = { overlay: overlay, mode: mode };
        _renderPopup();

        setTimeout(function () {
            overlay.classList.add("dp-popup-overlay--visible");
        }, 0);
    }

    function _closePopup() {
        if (!_popup) return;
        var overlay = _popup.overlay;
        overlay.classList.remove("dp-popup-overlay--visible");
        setTimeout(function () {
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }, 160);
        _popup = null;
    }

    function _closePopupImmediate() {
        if (!_popup) return;
        var overlay = _popup.overlay;
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        _popup = null;
    }

    function _renderPopup() {
        if (!_popup || !_active) return;
        var s       = _active;
        var overlay = _popup.overlay;

        // ── Nav arrows HTML ──
        var navHtml =
            '<div class="dp-popup-nav">' +
            '  <button class="dp-nav-btn dp-popup-prev" aria-label="Назад">‹</button>' +
            '  <div class="dp-popup-nav-label">' +
            (_popup.mode === "years" ? "Выбор года" : s.viewYear) +
            '  </div>' +
            '  <button class="dp-nav-btn dp-popup-next" aria-label="Вперёд">›</button>' +
            '</div>';

        var gridHtml = _popup.mode === "months"
            ? _buildMonths(s.viewYear, s.viewMonth)
            : _buildYears(s.viewYear);

        overlay.innerHTML =
            '<div class="dp-popup-backdrop"></div>' +
            '<div class="dp-popup">' +
            navHtml +
            '<div class="dp-popup-body">' + gridHtml + '</div>' +
            '</div>';

        // ── Backdrop closes popup ──
        overlay.querySelector(".dp-popup-backdrop").addEventListener("click", function (e) {
            e.stopPropagation();
            _closePopup();
        });

        // ── Prev / Next ──
        overlay.querySelector(".dp-popup-prev").addEventListener("click", function (e) {
            e.stopPropagation();
            if (_popup.mode === "months") { s.viewYear--; }
            else                          { s.viewYear -= 10; }
            _renderPopup();
        });
        overlay.querySelector(".dp-popup-next").addEventListener("click", function (e) {
            e.stopPropagation();
            if (_popup.mode === "months") { s.viewYear++; }
            else                          { s.viewYear += 10; }
            _renderPopup();
        });

        // ── Month clicks ──
        if (_popup.mode === "months") {
            overlay.querySelectorAll(".dp-month").forEach(function (el) {
                el.addEventListener("click", function (e) {
                    e.stopPropagation();
                    s.viewMonth = +el.dataset.month;
                    _closePopup();
                    _render();
                });
            });
        }

        // ── Year clicks → switch popup to months ──
        if (_popup.mode === "years") {
            overlay.querySelectorAll(".dp-year").forEach(function (el) {
                el.addEventListener("click", function (e) {
                    e.stopPropagation();
                    s.viewYear   = +el.dataset.year;
                    _popup.mode  = "months";
                    _renderPopup();
                });
            });
        }
    }

    // ── Render (always days mode) ──────────────────────────────
    function _render() {
        if (!_active) return;
        var s        = _active;
        var fmt = _getFormat(s.el);
        var selected = _parseDate(s.el.value, fmt);

        var headerCenter =
            '<span class="dp-title-month" id="dp-title-month">' +
            MONTHS_RU[s.viewMonth] + '</span>' +
            '<span class="dp-title-sep"> </span>' +
            '<span class="dp-title-year" id="dp-title-year">' + s.viewYear + '</span>';

        var body = _buildDays(s.viewYear, s.viewMonth, selected);

        s.wrap.innerHTML =
            '<div class="dp-header">' +
            '  <button class="dp-nav-btn" id="dp-prev" aria-label="Назад">‹</button>' +
            '  <div class="dp-title-wrap" id="dp-title-wrap">' + headerCenter + '</div>' +
            '  <button class="dp-nav-btn" id="dp-next" aria-label="Вперёд">›</button>' +
            '</div>' +
            '<div class="dp-body">' + body + '</div>';

        // ── Prev / Next month ──
        s.wrap.querySelector("#dp-prev").addEventListener("click", function (e) {
            e.stopPropagation();
            s.viewMonth--;
            if (s.viewMonth < 0) { s.viewMonth = 11; s.viewYear--; }
            _render();
        });
        s.wrap.querySelector("#dp-next").addEventListener("click", function (e) {
            e.stopPropagation();
            s.viewMonth++;
            if (s.viewMonth > 11) { s.viewMonth = 0; s.viewYear++; }
            _render();
        });

        // ── Title clicks → open popup ──
        s.wrap.querySelector("#dp-title-month").addEventListener("click", function (e) {
            e.stopPropagation();
            _openPopup("months");
        });
        s.wrap.querySelector("#dp-title-year").addEventListener("click", function (e) {
            e.stopPropagation();
            _openPopup("years");
        });

        // ── Day clicks ──
        s.wrap.querySelectorAll(".dp-day").forEach(function (el) {
            el.addEventListener("click", function (e) {
                e.stopPropagation();
                var d = new Date(+el.dataset.y, +el.dataset.m, +el.dataset.d);
                s.el.value = _formatDate(d, _getFormat(s.el));
                s.el.dispatchEvent(new Event("change", { bubbles: true }));
                _close();
            });
        });

        _position(s.wrap, s.el);
    }

    // ── Open ───────────────────────────────────────────────────
    function _open(el) {
        if (_active && _active.el === el) { _close(); return; }
        if (_active) _close();

        var parsed = _parseDate(el.value, _getFormat(el));
        var today  = new Date();

        var wrap = document.createElement("div");
        wrap.className = "dp-wrap";
        document.body.appendChild(wrap);

        _active = {
            el:        el,
            wrap:      wrap,
            viewYear:  parsed ? parsed.getFullYear() : today.getFullYear(),
            viewMonth: parsed ? parsed.getMonth()    : today.getMonth()
        };

        _render();
        setTimeout(function () {
            _position(wrap, el);
            wrap.classList.add("dp-visible");
        }, 0);
    }

    // ── Close ──────────────────────────────────────────────────
    function _close() {
        if (_popup) _closePopupImmediate();
        if (!_active) return;
        var wrap = _active.wrap;
        wrap.classList.remove("dp-visible");
        setTimeout(function () {
            if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
        }, 160);
        _active = null;
    }

    // ── Global listeners ───────────────────────────────────────
    document.addEventListener("click", function (e) {
        if (_popup) {
            if (_popup.overlay.contains(e.target)) return;
        }
        if (!_active) return;
        if (_active.wrap.contains(e.target)) return;
        if (_active.el === e.target) return;
        _close();
    }, true);

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            if (_popup) { _closePopup(); return; }
            if (_active) _close();
        }
    });

    // ── initElement ────────────────────────────────────────────
    function initElement(el) {
        if (!el || el._dpBound) return;
        el._dpBound = true;
        var handler = function (e) { e.stopPropagation(); _open(el); };
        el.addEventListener("click", handler);
        el.setAttribute("autocomplete", "off");
        el.setAttribute("readonly", "readonly");
        _bound.push({ el: el, handler: handler });
    }

    // ── init ───────────────────────────────────────────────────
    function init() {
        document.querySelectorAll("[data-datepicker]").forEach(initElement);
    }

    // ── destroy ────────────────────────────────────────────────
    function destroy() {
        if (_popup) _closePopupImmediate();
        _close();
        _bound.forEach(function (b) {
            b.el.removeEventListener("click", b.handler);
            b.el._dpBound = false;
            b.el.removeAttribute("readonly");
        });
        _bound = [];
    }

    // ── Public ─────────────────────────────────────────────────
    window.DatePicker = { init: init, initElement: initElement, destroy: destroy };

})();
