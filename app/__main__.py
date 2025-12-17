from app.services.ConversationAnalysisService import ConversationAnalysisService


def main():
    """Entry point for the Telcenter Core Base Service"""
    print("Starting Telcenter Core Base Service...")
    
    # Initialize S19 - Conversation Analysis Service
    s19_service = ConversationAnalysisService()
    s19_service.start()
    
    # Wait for service to complete
    s19_service.wait()


if __name__ == "__main__":
    main()
