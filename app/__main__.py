from app.services.ForwardedPartnerSelectionService import ForwardedPartnerSelectionService


def main():
    """Entry point for the Telcenter Core Base Service"""
    print("Starting Telcenter Core Base Service...")
    
    # Initialize S18 - Forwarded Partner Selection Service
    s18_service = ForwardedPartnerSelectionService()
    s18_service.start()
    
    # Wait for services to complete
    s18_service.wait()


if __name__ == "__main__":
    main()
