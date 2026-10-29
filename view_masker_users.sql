-- MASKER: view registered users and their connection statistics.
-- Open this file in MySQL Workbench and execute it.
-- Read-only: this script does not change the database.

USE masker_db;

SELECT
    username AS 'Username',
    username_hash AS 'Username Hash',
    client_ip AS 'IP Address',
    client_port AS 'Port',
    CASE WHEN is_online = 1 THEN 'Online' ELSE 'Offline' END AS 'Status',
    COALESCE(total_sent_media, 0) AS 'Files Sent',
    COALESCE(total_decoded_media, 0) AS 'Files Decoded',
    CASE WHEN ddos_status = 1 THEN 'Yes' ELSE 'No' END AS 'DDoS Flag',
    COALESCE(DATE_FORMAT(last_seen, '%Y-%m-%d %H:%i:%s'), 'Never logged in') AS 'Last Seen'
FROM users
ORDER BY username;
