"""PROJECT 테이블에 chat_room_id 컬럼(신규)을 실제 MySQL DB에 추가하는 1회성 스크립트.
이미 컬럼이 있으면 아무 것도 하지 않는다(재실행 안전).

실행: python -m scripts.add_project_chat_room_column
"""
from sqlalchemy import text
from app.db.database import engine


def main() -> None:
    with engine.connect() as conn:
        existing = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'project' "
                "AND column_name = 'chat_room_id'"
            )
        ).scalar()
        if existing:
            print("이미 존재함: project.chat_room_id - 건너뜀")
            return

        conn.execute(
            text(
                "ALTER TABLE project "
                "ADD COLUMN chat_room_id INT NULL COMMENT '자동 생성된 사업 협업 채팅방', "
                "ADD CONSTRAINT fk_project_chat_room FOREIGN KEY (chat_room_id) "
                "REFERENCES chat_room (room_id) ON DELETE SET NULL"
            )
        )
        conn.commit()
        print("완료: project.chat_room_id 컬럼 추가")


if __name__ == "__main__":
    main()
