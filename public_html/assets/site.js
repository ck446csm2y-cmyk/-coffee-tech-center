(function () {
  "use strict";

  var form = document.getElementById("lead-form");
  var status = document.getElementById("form-status");
  var year = document.getElementById("year");

  if (year) {
    year.textContent = String(new Date().getFullYear());
  }

  if (!form || !status) {
    return;
  }

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
