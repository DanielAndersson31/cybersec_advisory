import utils.logging as setup_logging
import logging


setup_logging()
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting the application")

if __name__ == "__main__":
    main()