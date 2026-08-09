<?php

declare(strict_types=1);

header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('X-Robots-Tag: noindex, nofollow, noarchive');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function escape(mixed $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function showError(int $status, string $message): never
{
    http_response_code($status);
    $safeMessage = escape($message);
    echo <<<HTML
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>Заявка — Кофе Тех Центр</title>
  <link rel="icon" href="/assets/kofe-tech-center-mark-v2.png">
  <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
  <main class="lead-page"><section class="lead-shell">
    <a class="standalone-brand" href="/"><img src="/assets/kofe-tech-center-mark-v2.png" alt=""><span><strong>Кофе Тех Центр</strong><small>Заявки с сайта</small></span></a>
    <h1>Заявка недоступна</h1><p>{$safeMessage}</p>
  </section></main>
</body>
</html>
HTML;
    exit;
}

$id = (string) ($_REQUEST['id'] ?? '');
$key = (string) ($_REQUEST['key'] ?? '');

if (!preg_match('/^\d{8}-\d{6}-[a-f0-9]{8}$/', $id) || !preg_match('/^[a-f0-9]{64}$/', $key)) {
    showError(404, 'Ссылка неверна или повреждена.');
}

$rootDir = dirname(__DIR__, 2);
$leadFile = $rootDir . '/private/leads/' . $id . '.json';
if (!is_file($leadFile)) {
    showError(404, 'Заявка не найдена. Возможно, она уже удалена.');
}

$lead = json_decode((string) file_get_contents($leadFile), true);
if (!is_array($lead) || !isset($lead['view_token_hash']) || !hash_equals((string) $lead['view_token_hash'], hash('sha256', $key))) {
    showError(404, 'Ссылка неверна или срок хранения заявки завершён.');
}

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    if (($_POST['action'] ?? '') !== 'delete') {
        showError(400, 'Неизвестное действие.');
    }
    if (@unlink($leadFile)) {
        showError(200, 'Заявка удалена с сервера. Эту страницу можно закрыть.');
    }
    showError(500, 'Не удалось удалить заявку. Повторите попытку позднее.');
}

$name = escape($lead['name'] ?? '—');
$phone = escape($lead['phone'] ?? '—');
$phoneLink = escape(preg_replace('/[^\d+]/', '', (string) ($lead['phone'] ?? '')) ?: '');
$equipment = escape($lead['equipment'] ?? '—');
$model = escape(($lead['model'] ?? '') !== '' ? $lead['model'] : 'Не указана');
$problem = nl2br(escape($lead['problem'] ?? '—'));
$contact = escape(($lead['contact'] ?? '') !== '' ? $lead['contact'] : 'Не указано');
$createdAt = escape($lead['created_at'] ?? '—');
$safeId = escape($id);
$safeKey = escape($key);

?><!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>Заявка <?= $safeId ?> — Кофе Тех Центр</title>
  <link rel="icon" href="/assets/kofe-tech-center-mark-v2.png">
  <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
  <main class="lead-page">
    <section class="lead-shell">
      <a class="standalone-brand" href="/"><img src="/assets/kofe-tech-center-mark-v2.png" alt=""><span><strong>Кофе Тех Центр</strong><small>Заявки с сайта</small></span></a>
      <p class="eyebrow"><span></span> Новая заявка</p>
      <h1>Заявка <?= $safeId ?></h1>
      <dl class="lead-details">
        <div><dt>Дата</dt><dd><?= $createdAt ?></dd></div>
        <div><dt>Имя</dt><dd><?= $name ?></dd></div>
        <div><dt>Телефон</dt><dd><a href="tel:<?= $phoneLink ?>"><?= $phone ?></a></dd></div>
        <div><dt>Оборудование</dt><dd><?= $equipment ?></dd></div>
        <div><dt>Марка и модель</dt><dd><?= $model ?></dd></div>
        <div><dt>Как ответить</dt><dd><?= $contact ?></dd></div>
        <div><dt>Описание</dt><dd><?= $problem ?></dd></div>
      </dl>
      <div class="lead-actions">
        <a class="button button-primary" href="tel:<?= $phoneLink ?>">Позвонить клиенту</a>
        <form method="post" onsubmit="return confirm('Удалить заявку с сервера? Это действие нельзя отменить.');">
          <input type="hidden" name="id" value="<?= $safeId ?>">
          <input type="hidden" name="key" value="<?= $safeKey ?>">
          <input type="hidden" name="action" value="delete">
          <button class="button button-danger" type="submit">Удалить заявку</button>
        </form>
      </div>
    </section>
  </main>
</body>
</html>
