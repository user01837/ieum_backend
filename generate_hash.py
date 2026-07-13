from passlib.context import CryptContext

# auth.py와 동일한 설정 사용
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_hash(password: str) -> str:
    """비밀번호를 bcrypt 해시로 변환합니다."""
    return pwd_context.hash(password)

if __name__ == "__main__":
    # 터미널에서 사용자에게 비밀번호 입력을 요청합니다.
    plain_password = input("해시로 변환할 비밀번호를 입력하세요: ")
    
    # 입력받은 비밀번호로 해시를 생성합니다.
    hashed_password = create_hash(plain_password)
    
    print("\n✅ 생성된 비밀번호 해시:")
    print(hashed_password)
    print("\n위 해시값을 복사하여 아래 SQL문의 '여기에_해시된_비밀번호_붙여넣기' 부분에 사용하세요.")
