(function () {
  "use strict";

  var form = document.getElementById("lead-form");
  var status = document.getElementById("form-status");
  var year = document.getElementById("year");
  var attributionStorageKey = "ktc_attribution_v1";
  var attributionKeys = [
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "avito_ad_id"
  ];

  if (year) {
    year.textContent = String(new Date().getFullYear());
  }

  if (!form || !status) {
    return;
  }

  function trimValue(value, maxLength) {
    return String(value || "").trim().slice(0, maxLength);
  }

  function safeReferrer() {
    if (!document.referrer) {
      return "";
    }

    try {
      var referrerUrl = new URL(document.referrer);
      return trimValue(referrerUrl.origin + referrerUrl.pathname, 300);
    } catch (error) {
      return "";
    }
  }

  function readStoredAttribution() {
    try {
      var stored = window.sessionStorage.getItem(attributionStorageKey);
      var parsed = stored ? JSON.parse(stored) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function captureAttribution() {
    var attribution = readStoredAttribution();
    var params = new URLSearchParams(window.location.search);

    attributionKeys.forEach(function (key) {
      var value = trimValue(params.get(key), 120);
      if (value) {
        attribution[key] = value;
      }
    });

    if (!attribution.source) {
      var referrer = safeReferrer();
      attribution.source = referrer.indexOf("avito.ru") !== -1 ? "avito" : "direct";
    }

    if (!attribution.landing_page) {
      attribution.landing_page = trimValue(window.location.pathname + window.location.search, 500);
    }
    if (!attribution.referrer) {
      attribution.referrer = safeReferrer();
    }

    try {
      window.sessionStorage.setItem(attributionStorageKey, JSON.stringify(attribution));
    } catch (error) {
      // Если sessionStorage недоступен, метки всё равно попадут в текущую заявку.
    }

    return attribution;
  }

  var attribution = captureAttribution();

  function showStatus(kind, message) {
    status.innerHTML = "";
    var paragraph = document.createElement("p");
    paragraph.className = "status-" + kind;
    paragraph.textContent = message;
    status.appendChild(paragraph);
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    if (!form.reportValidity()) {
      return;
    }

    var button = form.querySelector("button[type='submit']");
    var originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Отправляем…";
    status.innerHTML = "";

    var payload = {};
    new FormData(form).forEach(function (value, key) {
      payload[key] = value;
    });
    Object.keys(attribution).forEach(function (key) {
      payload[key] = attribution[key];
    });

    try {
      var response = await fetch("/api/lead.php", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(payload)
      });

      var result = await response.json().catch(function () { return {}; });

      if (!response.ok || !result.ok) {
        throw new Error(result.code || "REQUEST_FAILED");
      }

      form.reset();
      showStatus("success", "Заявка отправлена. Мы свяжемся с вами в рабочее время.");
    } catch (error) {
      showStatus("error", "Не удалось отправить заявку. Позвоните нам или напишите в мессенджер.");
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  });
})();
