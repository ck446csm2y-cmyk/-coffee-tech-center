<?php

declare(strict_types=1);

header('Content-Type: text/html; charset=utf-8');
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

function renderMessage(int $status, string $title, string $message, bool $success = false): never
{
    http_response_code($status);
    $safeTitle = escape($title);
    $safeMessage = escape($message);
    $action = $success ? '<a class="button button-primary" href="/">Открыть сайт</a>' : '';
    echo <<<HTML
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>{$safeTitle} — Кофе Тех Центр</title>
  <link rel="icon" href="/assets/kofe-tech-center-mark-v2.png">
  <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
  <main class="lead-page"><section class="lead-shell">
    <a class="standalone-brand" href="/"><img src="/assets/kofe-tech-center-mark-v2.png" alt=""><span><strong>Кофе Тех Центр</strong><small>Первоначальная настройка</small></span></a>
    <h1>{$safeTitle}</h1><p>{$safeMessage}</p>{$action}
  </section></main>
</body>
</html>
HTML;
    exit;
}

$configFile = dirname(__DIR__) . '/private/config.php';
if (!is_file($configFile)) {
    renderMessage(503, 'Настройка недоступна', 'Файл настроек не найден.');
}

$config = require $configFile;
if (!is_array($config)) {
    renderMessage(503, 'Настройка недоступна', 'Файл настроек повреждён.');
}

$expectedKey = (string) ($config['setup_key'] ?? '');
$providedKey = (string) ($_REQUEST['key'] ?? '');
if ($expectedKey === '') {
    renderMessage(410, 'Настройка завершена', 'Одноразовая страница уже отключена.');
}
if ($providedKey === '' || !hash_equals($expectedKey, $providedKey)) {
    renderMessage(404, 'Страница не найдена', 'Ссылка настройки неверна.');
}

$errors = [];
$values = [
    'operator_name' => (string) ($config['operator_name'] ?? ''),
    'operator_inn' => (string) ($config['operator_inn'] ?? ''),
    'operator_ogrnip' => (string) ($config['operator_ogrnip'] ?? ''),
    'operator_email' => (string) ($config['operator_email'] ?? ''),
    'operator_address' => (string) ($config['operator_address'] ?? 'г. Оренбург, ул. 9 Января, д. 58'),
    'telegram_chat_id' => (string) ($config['telegram_chat_id'] ?? ''),
];

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    foreach (array_keys($values) as $field) {
        $values[$field] = trim((string) ($_POST[$field] ?? ''));
    }
    $botToken = trim((string) ($_POST['telegram_bot_token'] ?? ''));

    if (mb_strlen($values['operator_name'], 'UTF-8') < 5 || mb_strlen($values['operator_name'], 'UTF-8') > 160) {
        $errors[] = 'Укажите полное ФИО индивидуального предпринимателя.';
    }
    if (!preg_match('/^(?:\d{10}|\d{12})$/', $values['operator_inn'])) {
        $errors[] = 'ИНН должен содержать 10 или 12 цифр.';
    }
    if (!preg_match('/^\d{15}$/', $values['operator_ogrnip'])) {
        $errors[] = 'ОГРНИП должен содержать 15 цифр.';
    }
    if (!filter_var($values['operator_email'], FILTER_VALIDATE_EMAIL)) {
        $errors[] = 'Укажите действующий адрес электронной почты.';
    }
    if (mb_strlen($values['operator_address'], 'UTF-8') < 8 || mb_strlen($values['operator_address'], 'UTF-8') > 250) {
        $errors[] = 'Укажите адрес для обращений.';
    }
    if (!preg_match('/^-?\d{5,20}$/', $values['telegram_chat_id'])) {
        $errors[] = 'Проверьте Telegram Chat ID.';
    }
    if (!preg_match('/^\d{5,}:[A-Za-z0-9_-]{20,}$/', $botToken)) {
        $errors[] = 'Проверьте токен Telegram-бота.';
    }

    if ($errors === []) {
        date_default_timezone_set('Asia/Yekaterinburg');
        $newConfig = [
            'setup_key' => '',
            'telegram_bot_token' => $botToken,
            'telegram_chat_id' => $values['telegram_chat_id'],
            'site_url' => 'https://kofetehcentr.ru',
            'operator_name' => $values['operator_name'],
            'operator_inn' => $values['operator_inn'],
            'operator_ogrnip' => $values['operator_ogrnip'],
            'operator_email' => $values['operator_email'],
            'operator_address' => $values['operator_address'],
            'policy_date' => date('d.m.Y'),
            'retention_days' => 365,
        ];
        $php = "<?php\n\ndeclare(strict_types=1);\n\nreturn " . var_export($newConfig, true) . ";\n";
        $temporaryFile = $configFile . '.tmp';

        if (file_put_contents($temporaryFile, $php, LOCK_EX) === false || !rename($temporaryFile, $configFile)) {
            @unlink($temporaryFile);
            $errors[] = 'Не удалось сохранить настройки. Проверьте права на папку private.';
        } else {
            @chmod($configFile, 0600);
            renderMessage(200, 'Настройка завершена', 'Реквизиты и Telegram сохранены. Одноразовая ссылка отключена.', true);
        }
    }
}

?><!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>Настройка сайта — Кофе Тех Центр</title>
  <link rel="icon" href="/assets/kofe-tech-center-mark-v2.png">
  <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
  <main class="lead-page">
    <section class="lead-shell">
      <a class="standalone-brand" href="/"><img src="/assets/kofe-tech-center-mark-v2.png" alt=""><span><strong>Кофе Тех Центр</strong><small>Первоначальная настройка</small></span></a>
      <p class="eyebrow"><span></span> Один раз перед запуском</p>
      <h1>Заполните реквизиты ИП и Telegram</h1>
      <p>Данные сохраняются прямо на вашем сервере Beget. Никому не отправляйте ссылку на эту страницу.</p>
      <?php if ($errors !== []): ?>
        <div class="draft-notice"><strong>Проверьте поля:</strong><ul><?php foreach ($errors as $error): ?><li><?= escape($error) ?></li><?php endforeach; ?></ul></div>
      <?php endif; ?>
      <form class="lead-form" method="post" autocomplete="off">
        <input type="hidden" name="key" value="<?= escape($providedKey) ?>">
        <label><span>Полное ФИО ИП</span><input name="operator_name" value="<?= escape($values['operator_name']) ?>" placeholder="Иванов Иван Иванович" required maxlength="160"></label>
        <div class="form-row">
          <label><span>ИНН</span><input name="operator_inn" value="<?= escape($values['operator_inn']) ?>" inputmode="numeric" required maxlength="12"></label>
          <label><span>ОГРНИП</span><input name="operator_ogrnip" value="<?= escape($values['operator_ogrnip']) ?>" inputmode="numeric" required maxlength="15"></label>
        </div>
        <label><span>Email для обращений</span><input name="operator_email" type="email" value="<?= escape($values['operator_email']) ?>" autocomplete="email" required maxlength="160"></label>
        <label><span>Адрес для обращений</span><input name="operator_address" value="<?= escape($values['operator_address']) ?>" required maxlength="250"></label>
        <div class="form-row">
          <label><span>Telegram Chat ID</span><input name="telegram_chat_id" value="<?= escape($values['telegram_chat_id']) ?>" inputmode="numeric" required maxlength="20"></label>
          <label><span>Токен Telegram-бота</span><input name="telegram_bot_token" type="password" placeholder="Вставьте токен из BotFather" required maxlength="200" autocomplete="new-password"></label>
        </div>
        <label class="consent"><input type="checkbox" required><span>Я проверил реквизиты и понимаю, что одноразовая ссылка отключится после сохранения.</span></label>
        <button class="button form-submit" type="submit">Сохранить и отключить настройку <span aria-hidden="true">→</span></button>
      </form>
    </section>
  </main>
</body>
</html>
