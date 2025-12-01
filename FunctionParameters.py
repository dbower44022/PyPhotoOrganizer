import logging
import sys

import utils

# Configure logging using shared utility
logger = utils.setup_logger(__name__, "app_error.log")


def example_function(params):
    if params:
        logger.info(f"The params passed = {params}")
    else:
        logger.info("No params passed")
        if "list" in params:
            function_list_parameter = params["list"]
        else:
            logger.info("Critical parameter 'List' is missing.  Using defaults")

    if  function_list_parameter:
        logger.info(f"function_list_parameter = {function_list_parameter}")
    else:
        function_list_parameter = ["default", "values"]

    logger.info(f"The final value of function_list_parameter = {function_list_parameter}")





if __name__ == '__main__':
    try:
        logger.info("Calling example_function with no parameter")
        parameters = {}
        example_function(parameters)


        set_parameter = {1,2,3}
        list_parameter = ['lemon', 'pear', 'watermelon', 'tomato']
        dictionary_parameter = {}
        dictionary_parameter["param1"] = "param one"
        dictionary_parameter["param2"] = "param Two"


        parameters["dictionary"] = dictionary_parameter
        parameters["list"] = list_parameter
        parameters["set"] = set_parameter
        parameters["string"] = "string"
        parameters["integer"] = 9
        logger.info("Calling example_function with multiple parameter")
        example_function(parameters)

    except Exception as e:
        logger.exception(f"\n process Failed : {sys.exc_info()} - {e}")