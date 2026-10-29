import os

from constants import BASE_DIR


def create_all_tables(db_manager):
    db_manager.create_table(
        "users",
        "("
        "username_hash VARCHAR(64) PRIMARY KEY, "
        "username VARCHAR(100), "
        "password_hash VARCHAR(64), "
        "client_ip VARCHAR(255), "
        "client_port INT, "
        "last_seen DATETIME, "
        "ddos_status BOOLEAN DEFAULT FALSE, "
        "is_online BOOLEAN DEFAULT FALSE, "
        "total_sent_media INT DEFAULT 0, "
        "total_decoded_media INT DEFAULT 0"
        ")"
    )

    columns = [
        (
            "client_ip",
            "VARCHAR(255)"
        ),
        (
            "client_port",
            "INT"
        ),
        (
            "last_seen",
            "DATETIME"
        ),
        (
            "ddos_status",
            "BOOLEAN DEFAULT FALSE"
        ),
        (
            "is_online",
            "BOOLEAN DEFAULT FALSE"
        ),
        (
            "total_sent_media",
            "INT DEFAULT 0"
        ),
        (
            "total_decoded_media",
            "INT DEFAULT 0"
        )
    ]

    for column_name, column_type in columns:
        db_manager.add_column_if_missing(
            "users",
            column_name,
            column_type
        )

    db_manager.create_table(
        "decrypted_media",
        "("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "user_id VARCHAR(64), "
        "media_type_id INT, "
        "path_to_decrypted_media VARCHAR(255)"
        ")"
    )

    db_manager.create_table(
        "media_menu",
        "("
        "id_media INT PRIMARY KEY, "
        "image_path VARCHAR(255), "
        "audio_path VARCHAR(255), "
        "video_path VARCHAR(255)"
        ")"
    )


def populate_media_menu(db_manager):
    rows = db_manager.get_all_rows(
        "media_menu"
    )

    if rows:
        return

    media = [
        (
            1,
            "poke.jpg",
            None,
            None
        ),
        (
            2,
            "mizperamon1.png",
            None,
            None
        )
    ]

    for row in media:
        db_manager.insert_row(
            "media_menu",
            "(id_media, image_path, audio_path, video_path)",
            "(%s, %s, %s, %s)",
            row
        )


def fix_old_paths(db_manager):
    rows = db_manager.get_all_rows(
        "media_menu"
    )

    for row in rows:
        media_id = row[0]
        image_path = row[1]
        audio_path = row[2]
        video_path = row[3]

        if image_path:
            image_path = os.path.basename(
                image_path.replace("\\", "/")
            )

        if audio_path:
            audio_path = os.path.basename(
                audio_path.replace("\\", "/")
            )

        if video_path:
            video_path = os.path.basename(
                video_path.replace("\\", "/")
            )

        db_manager.update_row(
            "media_menu",
            "id_media",
            media_id,
            [
                "image_path",
                "audio_path",
                "video_path"
            ],
            [
                image_path,
                audio_path,
                video_path
            ]
        )


def get_full_path(path_from_db):
    if not path_from_db:
        return None

    return os.path.join(
        BASE_DIR,
        path_from_db
    )