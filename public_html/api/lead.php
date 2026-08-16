<?php

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

function respond(int $status, array $payload): never
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function clean(mixed $value, int $maxLength): string
{
    $text = trim((string) $value);
    $text = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $text) ?? '';
    $text = str_replace(['<', '>'], '', $text);
    return mb_substr($text, 0, $maxLength, 'UTF-8');
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    respond(405, ['ok' => false, 'code' => 'METHOD_NOT_ALLOWED']);
}

$contentLength = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($contentLength > 25000) {
    respond(413, ['ok' => false, 'code' => 'PAYLOAD_TOO_LARGE']);
}

$raw = file_get_contents('php://input');
$body = json_decode($raw ?: '', true);
if (!is_array($body)) {
    respond(400, ['ok' => false, 'code' => 'INVALID_JSON']);
}

// Скрытое поле ловит простых спам-ботов, но для посетителя остаётся незаметным.
if (clean($body['website'] ?? '', 100) !== '') {
    respond(200, ['ok' => true]);
}

$name = clean($body['name'] ?? '', 80);
$phone = clean($body['phone'] ?? '', 30);
$equipment = clean($body['equipment'] ?? '', 100);
$model = clean($body['model'] ?? '', 100);
$problem = clean($body['problem'] ?? '', 1000);
$contact = clean($body['contact'] ?? '', 50);
$consent = clean($body['consent'] ?? '', 10);
$source = clean($body['source'] ?? '', 50);
$utmSource = clean($body['utm_source'] ?? '', 120);
$utmMedium = clean($body['utm_medium'] ?? '', 120);
$utmCampaign = clean($body['utm_campaign'] ?? '', 120);
$utmContent = clean($body['utm_content'] ?? '', 120);
$utmTerm = clean($body['utm_term'] ?? '', 120);
$avitoAdId = clean($body['avito_ad_id'] ?? '', 80);
$landingPage = clean($body['landing_page'] ?? '', 500);
$referrer = clean($body['referrer'] ?? '', 300);
$phoneDigits = preg_replace('/\D+/', '', $phone) ?? '';

if ($name === '' || strlen($phoneDigits) < 6 || $equipment === '' || $problem === '' || $consent !== 'yes') {
    respond(400, ['ok' => false, 'code' => 'INVALID_FIELDS']);
}

$rootDir = dirname(__DIR__, 2);
$privateDir = $rootDir . '/private';
$leadsDir = $privateDir . '/leads';
$rateDir = $privateDir . '/rate';
$configFile = $privateDir . '/config.php';

if (!is_file($configFile)) {
    respond(503, ['ok' => false, 'code' => 'SERVER_NOT_CONFIGURED']);
}

$config = require $configFile;
if (!is_array($config)) {
    respond(503, ['ok' => false, 'code' => 'SERVER_NOT_CONFIGURED']);
}

if (!is_dir($leadsDir) && !mkdir($leadsDir, 0700, true) && !is_dir($leadsDir)) {
    respond(500, ['ok' => false, 'code' => 'STORAGE_UNAVAILABLE']);
}
if (!is_dir($rateDir) && !mkdir($rateDir, 0700, true) && !is_dir($rateDir)) {
    respond(500, ['ok' => false, 'code' => 'STORAGE_UNAVAILABLE']);
}

// Не сохраняем IP-адрес: для ограничения частоты используется только односторонний хеш.
$remoteAddress = (string) ($_SERVER['REMOTE_ADDR'] ?? 'unknown');
$rateKey = hash('sha256', $remoteAddress . '|' . date('Y-m-d'));
$rateFile = $rateDir . '/' . $rateKey . '.json';
$now = time();
$windowStart = $now - 600;
$rateEvents = [];

$rateHandle = fopen($rateFile, 'c+');
if ($rateHandle !== false) {
    if (flock($rateHandle, LOCK_EX)) {
        $existing = stream_get_contents($rateHandle);
        $decoded = json_decode($existing ?: '[]', true);
        if (is_array($decoded)) {
            $rateEvents = array_values(array_filter($decoded, static fn ($event): bool => is_int($event) && $event >= $windowStart));
        }
        if (count($rateEvents) >= 5) {
            flock($rateHandle, LOCK_UN);
            fclose($rateHandle);
            respond(429, ['ok' => false, 'code' => 'RATE_LIMIT']);
        }
        $rateEvents[] = $now;
        rewind($rateHandle);
        ftruncate($rateHandle, 0);
        fwrite($rateHandle, json_encode($rateEvents));
        fflush($rateHandle);
        flock($rateHandle, LOCK_UN);
    }
    fclose($rateHandle);
    @chmod($rateFile, 0600);
}

date_default_timezone_set('Asia/Yekaterinburg');
$id = date('Ymd-His') . '-' . bin2hex(random_bytes(4));
$viewToken = bin2hex(random_bytes(32));
$lead = [
    'id' => $id,
    'created_at' => date(DATE_ATOM),
    'name' => $name,
    'phone' => $phone,
    'equipment' => $equipment,
    'model' => $model,
    'problem' => $problem,
    'contact' => $contact,
    'attribution' => array_filter([
        'source' => $source,
        'utm_source' => $utmSource,
        'utm_medium' => $utmMedium,
        'utm_campaign' => $utmCampaign,
        'utm_content' => $utmContent,
        'utm_term' => $utmTerm,
        'avito_ad_id' => $avitoAdId,
        'landing_page' => $landingPage,
        'referrer' => $referrer,
    ], static fn (string $value): bool => $value !== ''),
    'consent' => true,
    'view_token_hash' => hash('sha256', $viewToken),
];

$leadFile = $leadsDir . '/' . $id . '.json';
$encodedLead = json_encode($lead, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
if ($encodedLead === false || file_put_contents($leadFile, $encodedLead, LOCK_EX) === false) {
    respond(500, ['ok' => false, 'code' => 'STORAGE_UNAVAILABLE']);
}
@chmod($leadFile, 0600);

// Периодически удаляем старые заявки и файлы ограничения частоты.
if (random_int(1, 20) === 1) {
    $retentionDays = max(30, (int) ($config['retention_days'] ?? 365));
    $expiration = time() - ($retentionDays * 86400);
    foreach (glob($leadsDir . '/*.json') ?: [] as $file) {
        if ((filemtime($file) ?: time()) < $expiration) {
            @unlink($file);
        }
    }
    foreach (glob($rateDir . '/*.json') ?: [] as $file) {
        if ((filemtime($file) ?: time()) < time() - 172800) {
            @unlink($file);
        }
    }
}

$botToken = trim((string) ($config['telegram_bot_token'] ?? ''));
$chatId = trim((string) ($config['telegram_chat_id'] ?? ''));
$siteUrl = rtrim((string) ($config['site_url'] ?? 'https://kofetehcentr.ru'), '/');
$isConfigured = $botToken !== '' && $botToken !== 'ВСТАВЬТЕ_ТОКЕН_БОТА' && $chatId !== '';

if ($isConfigured && function_exists('curl_init')) {
    // В Telegram передаём только уведомление и защищённую ссылку. Имя и телефон остаются на сервере в РФ.
    $viewUrl = $siteUrl . '/admin/lead.php?id=' . rawurlencode($id) . '&key=' . rawurlencode($viewToken);
    $sourceLabel = $source !== '' ? $source : ($utmSource !== '' ? $utmSource : 'не определён');
    $message = "☕ Новая заявка — Кофе Тех Центр\n\nНомер: {$id}\nИсточник: {$sourceLabel}\nОткрыть заявку: {$viewUrl}";
    $curl = curl_init('https://api.telegram.org/bot' . $botToken . '/sendMessage');
    if ($curl !== false) {
        curl_setopt_array($curl, [
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 10,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_POSTFIELDS => json_encode(['chat_id' => $chatId, 'text' => $message], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
        ]);
        $telegramBody = curl_exec($curl);
        $telegramStatus = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        $telegramError = curl_error($curl);
        curl_close($curl);

        if ($telegramBody === false || $telegramStatus < 200 || $telegramStatus >= 300) {
            @file_put_contents($privateDir . '/notify-errors.log', date(DATE_ATOM) . " {$id} Telegram notification failed: {$telegramStatus} {$telegramError}\n", FILE_APPEND | LOCK_EX);
        }
    }
} elseif (!$isConfigured) {
    @file_put_contents($privateDir . '/notify-errors.log', date(DATE_ATOM) . " {$id} Telegram is not configured\n", FILE_APPEND | LOCK_EX);
}

respond(200, ['ok' => true, 'id' => $id]);
