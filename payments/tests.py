from django.test import TestCase
from payments.models import Payment
from orders.models import Order
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
class PaymentApprovedTestCase(TestCase):
    ''' Test case must be successfully '''
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@email.com',
            password='123456'
        )
        self.order = Order.objects.create(
            user = self.user,
            subtotal=15000,
            shipping_cost=5000
        )
        Payment.objects.create(
            order = self.order,
            payment_id = 777,
            mercado_pago_order_id = 'TEST_PAYMENT_ID',
            external_reference = 'None',
            payment_status = 'APPROVED',
            payment_amount = self.order.subtotal + self.order.shipping_cost,
            net_received_amount = 20000,
            taxes_amount = 5000,
            currency_id = 'COP',
            payment_method = 'ACCOUNT_MONEY',
            payment_type = 'CASH',
            payment_date = timezone.now(),
            #last_updated = models.DateTimeField(auto_now=True, blank=True, null=True)

            # Payer information
            payer_email = 'testpayer@email.com',
            payer_id = 'PAY4626',
            payer_identification_type = 'CC',
            payer_identification_number = '1005123456',
            payer_street_name = 'Test street 123 # 13 - 25',
            payer_street_number = '25',
            payer_zip_code = '110110'
        )

    def test_payment_is_valid(self):
        payment = Payment.objects.get(payment_id=777)
        self.assertEqual(payment.payment_status, 'APPROVED')

        
class PaymentFailedTestCase(TestCase):
    ''' Test case must be fail '''
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@email.com',
            password='123456'
        )
        self.order = Order.objects.create(
            user = self.user,
            subtotal=15000,
            shipping_cost=5000
        )
        Payment.objects.create(
            order = self.order,
            payment_id = 555,
            mercado_pago_order_id = 'TEST_PAYMENT_ID',
            external_reference = 'None',
            payment_status = 'APPROVED',
            payment_amount = self.order.subtotal + self.order.shipping_cost,
            net_received_amount = 20000,
            taxes_amount = 5000,
            currency_id = 'COP',
            payment_method = 'ACCOUNT_MONEY',
            payment_type = 'CASH',
            payment_date = timezone.now(),
            #last_updated = models.DateTimeField(auto_now=True, blank=True, null=True)

            # Payer information
            payer_email = 'testpayer@email.com',
            payer_id = 'PAY4626',
            payer_identification_type = 'CC',
            payer_identification_number = '1005123456',
            payer_street_name = 'Test street 123 # 13 - 25',
            payer_street_number = '25',
            payer_zip_code = '110110'
        )

    def test_payment_is_failed(self):
        payment = Payment.objects.get(payment_id=555)
        self.assertEqual(payment.payment_status, 'FAILED')
