"""
Main entry point for vAuto Feature Verification System.

This module initializes all components and orchestrates the verification process.
"""

import asyncio
import logging
import json
import os
import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
def setup_logging(log_level="INFO"):
    """
    Set up logging configuration.
    
    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_filename = os.path.join(log_dir, f"vauto_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(sys.stdout)
        ]
    )

# Import modules after logging is configured
def import_modules():
    """
    Import modules after logging is configured.
    
    Returns:
        tuple: Imported modules
    """
    from core.nova_engine import NovaActEngine
    from modules.authentication.auth_module import AuthenticationModule
    from modules.inventory.inventory_discovery import InventoryDiscoveryModule
    from modules.inventory.window_sticker_processor import WindowStickerProcessor
    from modules.inventory.checkbox_management import CheckboxManagementModule
    from modules.feature_mapping.feature_mapper import FeatureMapper, MappingLearner
    from modules.reporting.reporting import ReportingModule
    from modules.workflow import VerificationWorkflow
    
    return (
        NovaActEngine, AuthenticationModule, InventoryDiscoveryModule,
        WindowStickerProcessor, CheckboxManagementModule, FeatureMapper,
        MappingLearner, ReportingModule, VerificationWorkflow
    )

# Load configuration
def load_config():
    """
    Load configuration from JSON files.
    
    Returns:
        tuple: System config, dealership config, and feature mapping
    """
    config_dir = "configs"
    
    # Load system configuration
    with open(os.path.join(config_dir, "system_config.json"), 'r') as f:
        system_config = json.load(f)
    
    # Load dealership configuration
    with open(os.path.join(config_dir, "dealership_config.json"), 'r') as f:
        dealership_config = json.load(f)
    
    # Load feature mapping
    with open(os.path.join(config_dir, "feature_mapping.json"), 'r') as f:
        feature_mapping = json.load(f)
    
    return system_config, dealership_config, feature_mapping

# Main function
async def main(args):
    """
    Main entry point for the application.
    
    Args:
        args: Command-line arguments
    """
    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting vAuto Feature Verification System")
    
    try:
        # Load configuration
        system_config, dealership_config, feature_mapping = load_config()
        
        # Import modules
        (NovaActEngine, AuthenticationModule, InventoryDiscoveryModule,
        WindowStickerProcessor, CheckboxManagementModule, FeatureMapper,
        MappingLearner, ReportingModule, VerificationWorkflow) = import_modules()
        
        # Initialize components
        nova_engine = NovaActEngine(system_config)
        
        auth_module = AuthenticationModule(nova_engine, system_config)
        
        inventory_discovery = InventoryDiscoveryModule(
            nova_engine, auth_module, system_config
        )
        
        window_sticker_processor = WindowStickerProcessor(system_config)
        
        feature_mapper = FeatureMapper(system_config)
        
        mapping_learner = MappingLearner(feature_mapper)
        
        checkbox_management = CheckboxManagementModule(
            nova_engine, auth_module, feature_mapper, system_config
        )
        
        reporting = ReportingModule(system_config)
        
        workflow = VerificationWorkflow(
            nova_engine, auth_module, inventory_discovery, window_sticker_processor,
            feature_mapper, checkbox_management, reporting, system_config
        )
        
        # Run verification for specified dealership or all dealerships
        if args.dealership:
            # Find the specified dealership in config
            target_dealership = None
            for dealership in dealership_config:
                if dealership.get("dealer_id") == args.dealership or dealership.get("name") == args.dealership:
                    target_dealership = dealership
                    break
            
            if not target_dealership:
                logger.error(f"Dealership not found: {args.dealership}")
                return
            
            # Run verification for the specified dealership
            logger.info(f"Running verification for dealership: {target_dealership['name']}")
            result = await workflow.run_verification(target_dealership)
            
            if result.get("success"):
                logger.info(f"Verification completed successfully for {target_dealership['name']}")
                logger.info(f"Processed {result.get('vehicles_processed', 0)} vehicles with {result.get('successful_updates', 0)} successful updates")
            else:
                logger.error(f"Verification failed for {target_dealership['name']}: {result.get('error', 'Unknown error')}")
        
        elif args.test:
            # Run in test mode
            logger.info("Running in test mode")
            
            # Use the first dealership for testing
            if not dealership_config:
                logger.error("No dealerships configured")
                return
            
            test_dealership = dealership_config[0]
            logger.info(f"Using dealership for test: {test_dealership['name']}")
            
            # Limit to 1 vehicle for testing
            test_dealership["max_vehicles"] = 1
            
            result = await workflow.run_verification(test_dealership)
            
            if result.get("success"):
                logger.info("Test completed successfully")
                logger.info(f"Processed {result.get('vehicles_processed', 0)} vehicles with {result.get('successful_updates', 0)} successful updates")
            else:
                logger.error(f"Test failed: {result.get('error', 'Unknown error')}")
        
        else:
            # Run for all dealerships or set up scheduler
            if args.schedule:
                # Set up scheduler
                logger.info("Setting up scheduler")
                
                scheduler = AsyncIOScheduler()
                
                # Add jobs for each dealership
                for dealership in dealership_config:
                    if "schedule" not in dealership:
                        logger.warning(f"No schedule defined for dealership {dealership['name']}, skipping")
                        continue
                    
                    # Parse schedule
                    schedule = dealership["schedule"]
                    
                    logger.info(f"Scheduling verification for {dealership['name']}: {schedule}")
                    
                    # Add job to scheduler
                    scheduler.add_job(
                        workflow.run_verification,
                        'cron',
                        args=[dealership],
                        **schedule,
                        id=f"verification_{dealership['dealer_id']}"
                    )
                
                # Start the scheduler
                scheduler.start()
                logger.info("Scheduler started")
                
                # Keep the scheduler running
                try:
                    # Run forever
                    while True:
                        await asyncio.sleep(1)
                except (KeyboardInterrupt, SystemExit):
                    # Shutdown the scheduler on exit
                    logger.info("Shutting down scheduler")
                    scheduler.shutdown()
            
            else:
                # Run for all dealerships immediately
                logger.info(f"Running verification for all {len(dealership_config)} dealerships")
                
                all_results = []
                for dealership in dealership_config:
                    logger.info(f"Running verification for dealership: {dealership['name']}")
                    
                    result = await workflow.run_verification(dealership)
                    all_results.append(result)
                    
                    if result.get("success"):
                        logger.info(f"Verification completed successfully for {dealership['name']}")
                        logger.info(f"Processed {result.get('vehicles_processed', 0)} vehicles with {result.get('successful_updates', 0)} successful updates")
                    else:
                        logger.error(f"Verification failed for {dealership['name']}: {result.get('error', 'Unknown error')}")
                
                # Summarize results
                successful = len([r for r in all_results if r.get("success")])
                logger.info(f"Completed verification for {len(all_results)} dealerships ({successful} successful)")
    
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}", exc_info=True)
    
    finally:
        # Clean up resources
        if 'nova_engine' in locals():
            await nova_engine.close_browser()
        
        logger.info("vAuto Feature Verification System shutdown complete")

# Command-line argument parsing
def parse_args():
    """
    Parse command-line arguments.
    
    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="vAuto Feature Verification System")
    
    # Add arguments
    parser.add_argument(
        "--dealership", "-d",
        help="Run verification for a specific dealership by ID or name"
    )
    
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Run in test mode (limited to 1 vehicle)"
    )
    
    parser.add_argument(
        "--schedule", "-s",
        action="store_true",
        help="Run in scheduled mode using the schedules defined in dealership configuration"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )
    
    return parser.parse_args()

# Entry point
if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_args()
    
    # Run the main function
    asyncio.run(main(args))
