import os
import logging
import datetime

import utils

# Configure logging using shared utility
logger = utils.setup_logger(__name__, "test_routines.log")


if __name__ == '__main__':
    try:
        target_directory = "c:\\"
        no_year = False
        daily = True

        year = 2024
        month = 11
        day = 25

        if no_year:
            if daily:
                #ex: c:\2024-11\25
                target_folder = os.path.join(
                    target_directory, f"{year}-{month:02d}", f"{day:02d}"
                )
            else:
                #ex: c:\2024-11
                target_folder = os.path.join(target_directory, f"{year}-{month:02d}")
        else:
            if daily:
                #ex: c:\2024\11\25
                target_folder = os.path.join(
                    target_directory, str(year), f"{month:02d}", f"{day:02d}"
                )
            else:
                #ex: c:\2024\11
                target_folder = os.path.join(target_directory, str(year), f"{month:02d}")

        print(target_folder)

    except Exception as e:
        print(e)

    try:
        now = datetime.datetime.now()

        # Format the date components as two-digit strings
        year = now.strftime("%Y")  # Four-digit year (small y = two digit)
        month = now.strftime("%m")  # Two-digit month
        day = now.strftime("%d")  # Two-digit day
        logger.info(f"Year - {year}, Month - {month}, Day - {day}")
        logger.info(f"Type of day = {type(day)}, Month = {type(month)}, Year = {type(year)}")

        fyear = f"{now:%Y}"
        fmonth = f"{now:%m}"
        fday = f"{now:%d}"
        logger.info(f"Year - {fyear}, Month - {fmonth}, Day - {fday}")
        logger.info(f"Type of day = {type(fday)}, Month = {type(fmonth)}, Year = {type(fyear)}")

    except Exception as e:
        logger.exception(f"The error = {e}")

    try:
        # dictionary processing tests
        test_dict = {}
        test_dict["key1"] = None
        test_dict["key2"] = "Value"

        if test_dict.get('key1') == "Value":
            logger.info("The test for key1 Value worked!")
        elif test_dict.get('key1') == None:
            logger.info("the test for key1 None worked1!")

        if test_dict.get('key2') == "Value":
            logger.info("The test for key2 Value worked 2!")
        elif test_dict.get('key2') == None:
            logger.info("The test for key2 None (null) worked - 2")

        if test_dict.get('key3') == "Value":
            logger.info("The test for key3 Value worked 3!")
        elif  test_dict.get('key1') == None:
            logger.info("The test for key1 == None - 3 really did work, because the get  returned a null!")

    except Exception as e:
        logger.exception(f"The error occurred in the dictionary processing test = {e}")