"""
Workflow Module for vAuto Feature Verification System.

Handles:
- Orchestration of the overall verification process
- Coordination between different modules
- Error handling and retries
"""

import logging
import asyncio
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class VerificationWorkflow:
    """
    Main workflow for the vAuto Feature Verification System.
    """
    
    def __init__(self, nova_engine, auth_module, inventory_discovery, window_sticker_processor, 
                feature_mapper, checkbox_management, reporting, config):
        """
        Initialize the verification workflow.
        
        Args:
            nova_engine: Nova Act Engine instance
            auth_module: Authentication module instance
            inventory_discovery: Inventory discovery module instance
            window_sticker_processor: Window sticker processor instance
            feature_mapper: Feature mapper instance
            checkbox_management: Checkbox management module instance
            reporting: Reporting module instance
            config (dict): System configuration
        """
        self.nova_engine = nova_engine
        self.auth_module = auth_module
        self.inventory_discovery = inventory_discovery
        self.window_sticker_processor = window_sticker_processor
        self.feature_mapper = feature_mapper
        self.checkbox_management = checkbox_management
        self.reporting = reporting
        self.config = config
        
        # Create directories for logs and reports
        os.makedirs("logs", exist_ok=True)
        os.makedirs("reports", exist_ok=True)
        
        logger.info("Verification Workflow initialized")
    
    async def run_verification(self, dealership_config):
        """
        Run the verification process for a dealership.
        
        Args:
            dealership_config (dict): Dealership configuration
            
        Returns:
            dict: Results of the verification process
        """
        start_time = datetime.now()
        logger.info(f"Starting verification for {dealership_config['name']}")
        
        try:
            # Step 1: Login to vAuto
            logged_in = await self.auth_module.login(dealership_config.get("dealership_id"))
            if not logged_in:
                error_msg = f"Failed to log in for {dealership_config['name']}"
                logger.error(error_msg)
                await self.reporting.send_alert("Login Failed", error_msg, dealership_config)
                return {
                    "success": False,
                    "dealership": dealership_config['name'],
                    "error": error_msg,
                    "start_time": start_time,
                    "end_time": datetime.now()
                }
            
            # Step 2: Discover vehicles needing verification
            vehicles = await self.inventory_discovery.get_vehicles_needing_verification(
                dealership_config,
                dealership_config.get("max_vehicles")
            )
            
            if not vehicles:
                logger.info(f"No vehicles found needing verification for {dealership_config['name']}")
                return {
                    "success": True,
                    "dealership": dealership_config['name'],
                    "vehicles_processed": 0,
                    "results": [],
                    "start_time": start_time,
                    "end_time": datetime.now()
                }
            
            logger.info(f"Found {len(vehicles)} vehicles needing verification")
            
            # Step 3: Process each vehicle
            results = []
            for index, vehicle in enumerate(vehicles):
                try:
                    logger.info(f"Processing vehicle {index+1}/{len(vehicles)}: {vehicle.get('id')}")
                    
                    # Step 3a: Get window sticker URL
                    if not vehicle.get("window_sticker_url"):
                        logger.warning(f"No window sticker URL for vehicle {vehicle.get('id')}")
                        results.append({
                            "success": False,
                            "vehicle_id": vehicle.get("id"),
                            "error": "No window sticker URL",
                            **vehicle
                        })
                        continue
                    
                    # Step 3b: Extract features from window sticker
                    extracted_features = await self.window_sticker_processor.extract_features(
                        vehicle["window_sticker_url"]
                    )
                    
                    if not extracted_features:
                        logger.warning(f"No features extracted for vehicle {vehicle.get('id')}")
                        results.append({
                            "success": False,
                            "vehicle_id": vehicle.get("id"),
                            "error": "No features extracted from window sticker",
                            **vehicle
                        })
                        continue
                    
                    logger.info(f"Extracted {len(extracted_features)} features from window sticker")
                    
                    # Step 3c: Update checkboxes in vAuto
                    update_result = await self.checkbox_management.update_vehicle_checkboxes(
                        vehicle, extracted_features
                    )
                    
                    # Add the vehicle info to the result
                    update_result.update(vehicle)
                    
                    results.append(update_result)
                    
                except Exception as e:
                    logger.error(f"Error processing vehicle {vehicle.get('id')}: {str(e)}")
                    results.append({
                        "success": False,
                        "vehicle_id": vehicle.get("id"),
                        "error": str(e),
                        **vehicle
                    })
            
            # Step 4: Generate report
            report_result = await self.reporting.process_results(dealership_config, results)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Verification completed for {dealership_config['name']} in {duration:.2f} seconds")
            logger.info(f"Processed {len(vehicles)} vehicles with {len([r for r in results if r.get('success')])} successes")
            
            return {
                "success": True,
                "dealership": dealership_config['name'],
                "vehicles_processed": len(vehicles),
                "successful_updates": len([r for r in results if r.get('success')]),
                "results": results,
                "report": report_result.get("report_path") if report_result.get("success") else None,
                "email_sent": report_result.get("email_sent", False),
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration
            }
            
        except Exception as e:
            error_msg = f"Error during verification process: {str(e)}"
            logger.error(error_msg)
            
            # Send alert about system error
            await self.reporting.send_alert(
                "Verification Process Error",
                error_msg,
                dealership_config
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "success": False,
                "dealership": dealership_config['name'],
                "error": error_msg,
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration
            }
        finally:
            # Ensure browser is closed
            await self.nova_engine.close_browser()
