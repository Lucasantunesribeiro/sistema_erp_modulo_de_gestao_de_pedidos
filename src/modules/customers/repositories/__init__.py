from modules.customers.repositories.django_repository import CustomerDjangoRepository
from modules.customers.repositories.interfaces import ICustomerRepository

__all__ = ["ICustomerRepository", "CustomerDjangoRepository"]
