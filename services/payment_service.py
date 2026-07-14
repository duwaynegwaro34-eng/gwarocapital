from abc import ABC, abstractmethod
from datetime import datetime, timezone
import uuid


class PaymentGateway(ABC):
    @property
    @abstractmethod
    def provider(self):
        raise NotImplementedError

    @abstractmethod
    def create_payment(self, amount, currency, metadata):
        raise NotImplementedError


class MpesaGateway(PaymentGateway):
    provider = "mpesa"

    def create_payment(self, amount, currency, metadata):
        tx_ref = f"MPESA-{uuid.uuid4().hex[:12].upper()}"
        return {
            "provider": self.provider,
            "reference": tx_ref,
            "status": "PENDING",
            "message": "M-Pesa STK push initiated.",
            "amount": float(amount),
            "currency": currency,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class PayPalGateway(PaymentGateway):
    provider = "paypal"

    def create_payment(self, amount, currency, metadata):
        tx_ref = f"PAYPAL-{uuid.uuid4().hex[:12].upper()}"
        return {
            "provider": self.provider,
            "reference": tx_ref,
            "status": "PENDING",
            "message": "PayPal order created.",
            "amount": float(amount),
            "currency": currency,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class CardGateway(PaymentGateway):
    provider = "card"

    def create_payment(self, amount, currency, metadata):
        tx_ref = f"CARD-{uuid.uuid4().hex[:12].upper()}"
        return {
            "provider": self.provider,
            "reference": tx_ref,
            "status": "PENDING",
            "message": "Card checkout session created.",
            "amount": float(amount),
            "currency": currency,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class PlaceholderGateway(PaymentGateway):
    def __init__(self, provider_name, message="Pending Integration"):
        self._provider_name = provider_name
        self._message = message

    @property
    def provider(self):
        return self._provider_name

    def create_payment(self, amount, currency, metadata):
        tx_ref = f"{self.provider.upper()}-{uuid.uuid4().hex[:12].upper()}"
        return {
            "provider": self.provider,
            "reference": tx_ref,
            "status": "PENDING",
            "message": f"{self._message}",
            "amount": float(amount),
            "currency": currency,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class PaymentService:
    def __init__(self):
        self._providers = {
            "mpesa": MpesaGateway(),
            "paypal": PayPalGateway(),
            "card": CardGateway(),
            "visa": CardGateway(),
            "mastercard": CardGateway(),
            "apple_pay": PlaceholderGateway("apple_pay", message="Apple Pay integration pending"),
            "google_pay": PlaceholderGateway("google_pay", message="Google Pay integration pending"),
            "crypto": PlaceholderGateway("crypto", message="Crypto (USDT TRC20) integration pending"),
        }

    def providers(self):
        # Only expose currently supported payment providers.
        return sorted({"mpesa", "paypal", "card"})

    def create_payment(self, provider, amount, currency="USD", metadata=None):
        metadata = metadata or {}
        gateway = self._providers.get((provider or "").strip().lower())
        if not gateway:
            return {
                "ok": False,
                "error": "Unsupported payment provider.",
            }

        payload = gateway.create_payment(amount=amount, currency=currency, metadata=metadata)
        payload["ok"] = True
        return payload
