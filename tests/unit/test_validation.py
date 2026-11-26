"""Pure schema/unit tests: no HTTP and no database."""
import unittest
from pydantic import ValidationError
from app.schemas import OrderCreateIn, RegisterIn, StockAdjustmentIn
from app.security import hash_password, verify_password
class ValidationTests(unittest.TestCase):
 def test_password_salted_and_verifiable(self):
  a=hash_password('QA-unit-password');b=hash_password('QA-unit-password')
  self.assertNotEqual(a,b);self.assertNotEqual(a,'QA-unit-password')
  self.assertTrue(verify_password('QA-unit-password',a));self.assertFalse(verify_password('wrong',a))
 def test_bcrypt_long_suffix_rejected(self):
  p='я'*36;self.assertFalse(verify_password(p+'x',hash_password(p)))
 def test_courier_requires_address(self):
  with self.assertRaises(ValidationError):OrderCreateIn(delivery_method='courier',contact_phone='+79990001234')
 def test_pickup_rejects_address(self):
  with self.assertRaises(ValidationError):OrderCreateIn(delivery_method='pickup',pickup_point_id=1,delivery_address='Address',contact_phone='+79990001234')
 def test_registration_blank_name(self):
  with self.assertRaises(ValidationError):RegisterIn(email='qa@example.com',password='Strong-2026',full_name='   ')
 def test_stock_zero_rejected(self):
  with self.assertRaises(ValidationError):StockAdjustmentIn(delta=0,comment='QA')
if __name__=='__main__':unittest.main(verbosity=2)
