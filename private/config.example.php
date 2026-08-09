<?php

declare(strict_types=1);

return [
    // Скопируйте файл как private/config.php и заполните только на сервере.
    // Никогда не добавляйте private/config.php в GitHub.
    'setup_key' => '',
    'telegram_bot_token' => '',
    'telegram_chat_id' => '',
    'site_url' => 'https://kofetehcentr.ru',
    'operator_name' => '',
    'operator_inn' => '',
    'operator_ogrnip' => '',
    'operator_email' => '',
    'operator_address' => '',
    'policy_date' => '',
    // Заявки старше указанного срока автоматически удаляются с сервера.
    'retention_days' => 365,
];
