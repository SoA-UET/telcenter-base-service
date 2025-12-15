"""
Test script for S11 Local Knowledge Service
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing S11 service imports...")
    
    try:
        from app.services.s11_local_knowledge_service import LocalKnowledgeService
        print("✓ LocalKnowledgeService imported successfully")
    except Exception as e:
        print(f"✗ Failed to import LocalKnowledgeService: {e}")
        return False
    
    try:
        from app.services.s11_local_knowledge_service.models import Package, FAQ
        print("✓ Models (Package, FAQ) imported successfully")
    except Exception as e:
        print(f"✗ Failed to import models: {e}")
        return False
    
    try:
        from app.services.s11_local_knowledge_service.database import MongoDBClient
        print("✓ MongoDBClient imported successfully")
    except Exception as e:
        print(f"✗ Failed to import MongoDBClient: {e}")
        return False
    
    try:
        from app.controllers.v1 import local_knowledge
        print("✓ H28 controller imported successfully")
    except Exception as e:
        print(f"✗ Failed to import H28 controller: {e}")
        return False
    
    print("\n✓ All imports successful!")
    return True


def test_models():
    """Test model serialization"""
    print("\nTesting models...")
    
    from app.services.s11_local_knowledge_service.models import Package, FAQ
    
    # Test Package
    pkg = Package(
        partner_id=1,
        code="SD70",
        meta_data={
            "payment_type": "Trả trước",
            "price": 70000,
            "cycle_days": 30
        },
        id=1
    )
    
    pkg_dict = pkg.to_dict()
    print(f"✓ Package serialization: {pkg_dict}")
    
    pkg_restored = Package.from_dict(pkg_dict)
    print(f"✓ Package deserialization: code={pkg_restored.code}")
    
    # Test FAQ
    faq = FAQ(
        partner_id=1,
        question="Test question?",
        answer="Test answer",
        category="Test",
        id=1
    )
    
    faq_dict = faq.to_dict()
    print(f"✓ FAQ serialization: {faq_dict}")
    
    faq_restored = FAQ.from_dict(faq_dict)
    print(f"✓ FAQ deserialization: question={faq_restored.question}")
    
    print("\n✓ All model tests passed!")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("S11 Local Knowledge Service - Test Suite")
    print("=" * 60)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test models
    if not test_models():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
