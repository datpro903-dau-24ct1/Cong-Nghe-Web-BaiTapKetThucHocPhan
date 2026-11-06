"""Các hàm đọc dữ liệu tài khoản (không ghi)."""


def list_addresses(user):
    """Địa chỉ của user: mặc định trước, rồi mới nhất trước."""
    return user.addresses.all()


def get_user_address(user, pk):
    """Địa chỉ theo pk nhưng chỉ khi thuộc về user; ngược lại trả về None."""
    return user.addresses.filter(pk=pk).first()