/* Изолированный фрейм для чужой разметки.
 *
 * ЗАЧЕМ. Свёрстанный HTML в портале приходит из двух мест: страницы кабинета
 * (задача 706, блок 102) и описания задачи (блок 2332). В обоих случаях его
 * может править клиент, а рядом — в адресе страницы — лежит магический токен
 * доступа к порталу. Отрисуй мы такую разметку в самой странице, скрипт внутри
 * прочитал бы токен из адреса и унёс наружу. Песочница без allow-same-origin
 * отрезает и адрес родителя, и его память.
 *
 * ПОЧЕМУ ОТДЕЛЬНЫМ ФАЙЛОМ. Механика жила в partner.js и была намертво привязана
 * к области документа портала: наблюдатель следил за #content, чтобы снять
 * слушатель сообщений. В слайдере задач такого узла нет — наблюдатель повис бы
 * на чужом элементе, слушатель не снялся бы никогда, и каждое открытие задачи
 * оставляло бы живой обработчик. Копировать механику вторым экземпляром нельзя
 * по обычной причине: починят в одном месте.
 *
 * Подключается и порталом, и китом задач — кит работает и на отдельной
 * странице, без partner.js.
 */
(function (global) {
  "use strict";

  /**
   * @param {string} html — разметка целиком
   * @param {Element} watchNode — узел, из которого фрейм однажды исчезнет;
   *        по этому событию снимается слушатель сообщений
   * @param {string} [className] — класс фрейма
   * @param {function} [onTask] — что делать по просьбе «открой задачу».
   * @param {function} [onOpen] — что делать по просьбе «открой документ».
   *        Фрейм только просит; решает портал, и он же проверяет, что путь
   *        вообще есть в дереве. Не задан — просьбы игнорируются.
   * @param {function} [onStatuses] — единственный обмен С ОТВЕТОМ. Возвращает
   *        (или обещает) карту «ключ панели → статус задачи». Не задан —
   *        страница остаётся без полосы прогресса, и это рабочий случай:
   *        кит задач рисует описания тем же фреймом, а прогресса у описания нет.
   */
  function buildSandboxFrame(html, watchNode, className, onOpen, onTask, onStatuses) {
    const frame = document.createElement("iframe");
    frame.className = className || "ep-page-frame";
    // allow-same-origin НЕ ставим никогда — это и есть песочница: скрипт внутри
    // не достаёт до адреса родителя, где лежит магический токен.
    //
    // Пара popup-флагов работает только вместе. Первый разрешает открыть
    // вкладку — без него ссылка не реагирует МОЛЧА, и человек решает, что
    // кабинет сломан. Второй снимает песочницу с открытого: без него чужой сайт
    // откроется с урезанными правами и, скорее всего, не заработает.
    frame.setAttribute(
      "sandbox",
      "allow-scripts allow-popups allow-popups-to-escape-sandbox"
    );
    frame.setAttribute("title", "Страница материала");

    // Разметка следует теме КАБИНЕТА, а не системы читателя: иначе светлая
    // система дала бы белую страницу внутри тёмного портала. Контракт:
    // тёмные токены на голом :root, светлые под [data-theme="light"].
    const theme = document.documentElement.getAttribute("data-theme") || "dark";

    // Ссылки открываются новой вкладкой без правки самой разметки: страницы
    // собираются скриптом, а описания задач правит клиент — требовать target
    // у каждого автора нельзя.
    const baseTag = '<base target="_blank">';

    const bootstrap =
      "<script>(function(){" +
      "document.documentElement.setAttribute('data-theme'," + JSON.stringify(theme) + ");" +
      // rel=noopener ставится КОДОМ, а не по доброй воле автора. Без него
      // открытая вкладка получает window.opener — ссылку на окно портала, в
      // адресе которого магический токен, и может его прочитать.
      // Тот же обход ставит rel внешним ссылкам и перехватывает внутренние.
      // Один обход, а не два наблюдателя на одном узле: второй дал бы двойную
      // обработку клика.
      "function rel(){document.querySelectorAll('a[href]').forEach(function(a){" +
      "if(a.dataset.epBound)return;a.dataset.epBound='1';" +
      // Внутренняя ссылка помечена якорем #ep/NNN. Обычным href её сделать
      // нельзя: <base target=_blank> увёл бы её новой вкладкой на адрес
      // портала — с магическим токеном в строке, который осел бы в истории
      // браузера и в реферере (задача 706, блок 226).
      "var h=a.getAttribute('href')||'';" +
      "if(h.indexOf('#ep/')===0){a.addEventListener('click',function(e){" +
      "e.preventDefault();parent.postMessage({t:'ep-open',path:h.slice(1)},'*');});return;}" +
      // Ссылка на задачу этого же кабинета. Тот же приём: перехват до перехода,
      // иначе <base target=_blank> увёл бы её новой вкладкой на адрес портала.
      "if(h.indexOf('#task/')===0){a.addEventListener('click',function(e){" +
      "e.preventDefault();parent.postMessage({t:'ep-task',id:h.slice(6)},'*');});return;}" +
      "a.rel=(a.rel?a.rel+' ':'')+'noopener noreferrer';});}" +
      "if(document.readyState!=='loading')rel();else addEventListener('DOMContentLoaded',rel);" +
      "new MutationObserver(rel).observe(document.documentElement,{childList:true,subtree:true});" +
      "function s(){parent.postMessage({t:'ep-page-height'," +
      "h:document.documentElement.scrollHeight},'*');}" +
      "if(document.readyState!=='loading')s();else addEventListener('DOMContentLoaded',s);" +
      "addEventListener('load',s);new ResizeObserver(s).observe(document.documentElement);" +
      // Живой прогресс. Первый обмен протокола С ОТВЕТОМ: спрашиваем статусы
      // задач по ключам панелей, портал отвечает картой. Цифру нельзя запекать
      // при сборке — она протухает к следующей встрече (задача 721, блок 209).
      //
      // Просим ТОЛЬКО когда есть что заполнять: пятнадцать старых материалов
      // кабинета панелей не имеют, и без этой проверки каждое их открытие
      // дёргало бы портал впустую.
      //
      // Высоту после заполнения не шлём — ResizeObserver выше уже висит
      // на documentElement и пересчитает сам.
      "var P=document.querySelector('[data-prog]');" +
      "if(P){addEventListener('message',function(e){" +
      "if(e.source!==parent||!e.data||e.data.t!=='ep-status')return;" +
      "var m=e.data.map||{},L={done:'готово',doing:'в работе',todo:'осталось'};" +
      "var c={done:0,doing:0,todo:0},n=0;" +
      "document.querySelectorAll('.toc li[data-key]').forEach(function(li){" +
      "var st=m[li.getAttribute('data-key')];if(!L[st])return;" +
      "var b=li.querySelector('.st');if(b){b.className='st '+st;b.textContent=L[st];}});" +
      // Считаем по панелям ЭТОГО документа, а не по карте: карта несёт все
      // задачи кабинета с ключом, включая чужие документы. На пробном портале
      // это дало «0 из 8» там, где панелей три — поймано замером.
      //
      // Панель без задачи в счёт не идёт: её статус нам неизвестен, и записать
      // её в «осталось» значило бы выдать незнание за факт.
      "document.querySelectorAll('section[data-key]').forEach(function(s){" +
      "var st=m[s.getAttribute('data-key')];if(L[st]){c[st]++;n++;}});" +
      // Ответ пустой — полоса остаётся скрытой. Показать «0 из 0» значило бы
      // соврать про документ, статусы которого портал не знает.
      "if(!n)return;" +
      "P.querySelector('.nm').textContent='Сделано по этому документу';" +
      "P.querySelector('.qt').textContent=c.done+' из '+n;" +
      "P.querySelector('.fl').style.width=Math.round(c.done/n*100)+'%';" +
      "P.querySelector('.leg').textContent=" +
      "'готово '+c.done+' · в работе '+c.doing+' · осталось '+c.todo;" +
      "P.removeAttribute('hidden');});" +
      "parent.postMessage({t:'ep-status?'},'*');}" +
      "})();<\/script>";

    // Общий стиль кабинета впрыскивается порталом, а не несётся страницей.
    // ДО разметки — тогда собственный <style> старых материалов идёт позже
    // и перекрывает общий, и пятнадцать существующих страниц не меняются
    // (задача 721, блок 101). Файла нет — фрейм собирается как раньше.
    // Шрифты грузит портал, а не страница. До этого загрузка жила в <link>
    // внутри каждой страницы — блок 101 вынес стиль и оставил её там. Собранная
    // сборщиком страница шрифтов не несла вовсе и падала на системный: замер
    // показывал «Inter», потому что он стоял на машине, а document.fonts был пуст
    // (задача 721, блок 301).
    //
    // Ссылкой, а не встраиванием: три семейства в наборе весов — сотни килобайт,
    // и фреймов на странице бывает несколько. Ссылка кэшируется один раз.
    // Цена — зависимость от сети, поэтому в стиле у каждой роли настоящий
    // запасной стек.
    const fontsTag =
      '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
      '<link rel="stylesheet" href="https://fonts.googleapis.com/css2' +
      '?family=Bitter:wght@600;700' +
      '&family=Inter:wght@400;500;600;700;800' +
      '&family=JetBrains+Mono:wght@400;500' +
      '&display=swap">';

    const styleTag = global.KABINET_PAGE_CSS
      ? "<style>" + global.KABINET_PAGE_CSS + "</style>"
      : "";

    frame.srcdoc = baseTag + fontsTag + styleTag + html + bootstrap;

    // Высоту принимаем только от этого фрейма: окно получает сообщения от кого
    // угодно, и чужое число здесь схлопнуло бы страницу.
    const onMessage = (e) => {
      // Источник сверяется ПЕРЕД разбором: окно принимает сообщения от кого
      // угодно, и чужое здесь получило бы управление порталом.
      if (e.source !== frame.contentWindow) return;
      if (!e.data) return;
      if (e.data.t === "ep-page-height") {
        const h = Number(e.data.h);
        if (h > 0) frame.style.height = h + "px";
        return;
      }
      if (e.data.t === "ep-open" && typeof onOpen === "function") {
        const path = String(e.data.path || "");
        if (path) onOpen(path);
        return;
      }
      if (e.data.t === "ep-task" && typeof onTask === "function") {
        // Значение уходит строкой: раньше это был только номер задачи, теперь
        // ещё и стабильный ключ панели документа. Номер свой в каждом кабинете —
        // документ с номером нельзя выдать двум клиентам (задача 721, блок 102).
        //
        // Проверка остаётся, но меняет смысл: фрейм — недоверенный источник, и
        // это единственный фильтр на пути. Пропускаем непустую строку разумной
        // длины, а не «что угодно».
        const key = String(e.data.id || "").trim();
        if (key && key.length <= 64) onTask(key);
        return;
      }
      if (e.data.t === "ep-status?" && typeof onStatuses === "function") {
        // Ответ уходит в песочницу с непрозрачным источником, поэтому
        // targetOrigin может быть только "*" — сузить некуда. Отсюда правило:
        // в ответе ровно карта «ключ → статус» и ничего больше. Ни номеров
        // задач, ни сроков, ни исполнителей: щель протокола не место для
        // выдачи данных, которых на странице нет.
        Promise.resolve()
          .then(() => onStatuses())
          .then((map) => {
            if (!map || !frame.contentWindow) return;
            frame.contentWindow.postMessage({ t: "ep-status", map }, "*");
          })
          // Не ответить — законный исход: полоса просто не появится, документ
          // читается как раньше. Ронять портал из-за неё нельзя.
          .catch(() => {});
      }
    };
    window.addEventListener("message", onMessage);

    // Слушатель снимается, когда фрейм ушёл из документа: открытие десяти
    // материалов подряд не должно оставить десять живых обработчиков.
    if (watchNode) {
      new MutationObserver((_, obs) => {
        if (!frame.isConnected) {
          window.removeEventListener("message", onMessage);
          obs.disconnect();
        }
      }).observe(watchNode, { childList: true, subtree: true });
    }

    return frame;
  }

  global.buildSandboxFrame = buildSandboxFrame;
})(window);
