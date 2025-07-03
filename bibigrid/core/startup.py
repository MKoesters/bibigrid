"""
Contains main method. Interprets command line, sets logging and starts corresponding action.
"""
import click
import logging
import math
import os
import sys
import time
import traceback
from types import SimpleNamespace
import yaml

from bibigrid.core.actions import check, create, ide, list_clusters, terminate, update, version
from bibigrid.core.utility import command_line_interpreter
from bibigrid.core.utility.handler import configuration_handler, provider_handler
from bibigrid.core.utility.paths.basic_path import CLUSTER_MEMORY_PATH
import logging
VERBOSITY_LIST = [logging.WARNING, logging.INFO, logging.DEBUG]



def setup_logger(
    name="bibigrid",
    log_file="bibigrid.log",
    console_level=None,
    file_level=logging.DEBUG,
    logger_format="%(asctime)s [%(levelname)s] %(message)s"
):
    """
    Set up a logger with both console and file handlers, including a custom PRINT level.

    Args:
        name (str): Logger name.
        log_file (str): Path to the log file.
        console_level (int): Logging level for the console handler.
        file_level (int): Logging level for the file handler.
        logger_format (str): Log message format.

    Returns:
        logging.Logger: Configured logger.
    """
    PRINT_LEVEL = 42
    logging.addLevelName(PRINT_LEVEL, "PRINT")

    def print_log(self, message, *args, **kwargs):
        if self.isEnabledFor(PRINT_LEVEL):
            self._log(PRINT_LEVEL, message, args, **kwargs)
    logging.Logger.print = print_log

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Allow all messages through

    # Remove existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(logger_format))

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(logger_format))

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger



def get_cluster_id_from_mem():
    """
        Reads the cluster_id of the last created cluster and returns it. Used if no cluster_id is given.

    @return: cluster_id. If no mem file can be found, the file is not a valid yaml file or doesn't contain a cluster_id,
    it returns none.
    """
    if os.path.isfile(CLUSTER_MEMORY_PATH):
        try:
            with open(CLUSTER_MEMORY_PATH, mode="r", encoding="UTF-8") as cluster_memory_file:
                mem_dict = yaml.safe_load(stream=cluster_memory_file)
                return mem_dict.get("cluster_id")
        except yaml.YAMLError as exc:
            LOG.warning("Couldn't read configuration %s: %s", CLUSTER_MEMORY_PATH, exc)
    LOG.warning(f"Couldn't find cluster memory path {CLUSTER_MEMORY_PATH}")
    return None


def set_logger_verbosity(logger, verbosity):
    """
    Sets verbosity, format and handler.
    @param verbosity: level of verbosity
    @return:
    """
    capped_verbosity = min(verbosity, len(VERBOSITY_LIST) - 1)
    logger.setLevel(VERBOSITY_LIST[capped_verbosity])
    logger.debug(f"Logging verbosity set to {capped_verbosity}")


# pylint: disable=too-many-nested-blocks,too-many-branches, too-many-statements
def run_action(args, configurations, config_path):
    """
    Uses args to decide which action will be executed and executes said action.
    @param args: command line arguments
    @param configurations: list of configurations (dicts)
    @param config_path: path to configurations-file
    @return:
    """
    if args.version:
        logger.info("Action version selected")
        version.version(logger)
        return 0

    start_time = time.time()
    exit_state = 0
    try:
        providers = provider_handler.get_providers(configurations, logger)
        if providers:
            if args.list:
                logger.info("Action list selected")
                exit_state = list_clusters.log_list(args.cluster_id, providers, logger)
            elif args.check:
                logger.info("Action check selected")
                exit_state = check.check(configurations, providers, logger)
            elif args.create:
                logger.info("Action create selected")
                creator = create.Create(providers=providers, configurations=configurations, log=logger, debug=args.debug,
                                        config_path=config_path)
                logger.log(42, "Creating a new cluster takes about 10 or more minutes depending on your cloud provider "
                            "and your configuration. Please be patient.")
                exit_state = creator.create()
            else:
                if not args.cluster_id:
                    args.cluster_id = get_cluster_id_from_mem()
                    logger.info("No cid (cluster_id) specified. Defaulting to last created cluster: %s",
                             args.cluster_id or 'None found')
                if args.cluster_id:
                    if args.terminate:
                        logger.info("Action terminate selected")
                        exit_state = terminate.terminate(cluster_id=args.cluster_id, providers=providers, log=logger,
                                                         debug=args.debug)
                    elif args.ide:
                        logger.info("Action ide selected")
                        exit_state = ide.ide(args.cluster_id, providers[0], configurations[0], logger)
                    elif args.update:
                        logger.info("Action update selected")
                        creator = create.Create(providers=providers, configurations=configurations, log=logger,
                                                debug=args.debug,
                                                config_path=config_path, cluster_id=args.cluster_id)
                        exit_state = update.update(creator, logger)
            for provider in providers:
                provider.close()
        else:
            exit_state = 1
    except Exception as err:  # pylint: disable=broad-except
        if args.debug:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        else:
            logger.error(err)
        exit_state = 2
    time_in_s = time.time() - start_time
    logger.log(42, f"--- {math.floor(time_in_s / 60)} minutes and {round(time_in_s % 60, 2)} seconds ---")
    return exit_state


# def main():
#     """
#     Interprets command line, sets logger, reads configuration and runs selected action. Then exits.
#     @return:
#     """
#     logging.basicConfig(format=LOGGER_FORMAT)
#     # LOG.addHandler(logging.StreamHandler())  # stdout
#     LOG.addHandler(logging.FileHandler("bibigrid.log"))  # file
#     args = command_line_interpreter.interpret_command_line()
#     set_logger_verbosity(args.verbose)

#     configurations = configuration_handler.read_configuration(LOG, args.config_input)
#     if not configurations:
#         sys.exit(1)
#     configurations = configuration_handler.merge_configurations(
#         user_config=configurations,
#         default_config_path=args.default_config_input,
#         enforced_config_path=args.enforced_config_input,
#         log=LOG
#     )
#     if configurations:
#         sys.exit(run_action(args, configurations, args.config_input))


# if __name__ == "__main__":
#     main()

logger = setup_logger(console_level=1)
set_logger_verbosity(logger, 1)

@click.command()
@click.option('-h', '--help', is_flag=True, help='Show this message and exit.')
@click.option('-v', '--verbosity', type=int, default=1, help='Verbosity level')
@click.option('-d', '--debug', is_flag=True, help='Enable debug mode.')
@click.option('-i', '--config-input', type=click.Path(), help='Path to user configuration.')
@click.option('-di', '--default-config-input', type=click.Path(), help='Path to default configuration.')
@click.option('-ei', '--enforced-config-input', type=click.Path(), help='Path to enforced configuration.')
@click.option('-cid', '--cluster-id', help='Cluster ID.')
@click.option('-V', '--version', is_flag=True, help='Show version and exit.')
@click.option('-t', '--terminate', is_flag=True, help='Terminate cluster.')
@click.option('-c', '--create', is_flag=True, help='Create cluster.')
@click.option('-l', '--list', is_flag=True, help='List clusters.')
@click.option('-ch', '--check', is_flag=True, help='Check cluster.')
@click.option('-ide', '--ide', is_flag=True, help='IDE mode.')
@click.option('-u', '--update', is_flag=True, help='Update cluster.')
def main(help, verbosity, debug, config_input, default_config_input, enforced_config_input, cluster_id,
         version, terminate, create, list, check, ide, update):
    """
    Interprets command line, sets logger, reads configuration and runs selected action. Then exits.
    """
    # logging.basicConfig(format=LOGGER_FORMAT)
    # LOG.addHandler(logging.FileHandler("bibigrid.log"))
    # breakpoint()
    # logger = setup_logger(console_level=verbosity)

    # Enforce that exactly one action is selected
    actions = [version, terminate, create, list, check, ide, update]
    if sum(actions) != 1:
        # Click's fail() prints usage and exits with error
        ctx = click.get_current_context()
        ctx.fail("One (and only one) of the arguments -V/--version -t/--terminate -c/--create -l/--list -ch/--check -ide/--ide -u/--update is required")

    # set_logger_verbosity(logger, verbosity)

    # Replace with your actual configuration handler
    configurations = configuration_handler.read_configuration(logger, config_input)
    if not configurations:
        sys.exit(1)

    if default_config_input is None:
        default_config_input = ""
    if enforced_config_input is None:
        enforced_config_input = ""
    configurations = configuration_handler.merge_configurations(
        user_config=configurations,
        default_config_path=default_config_input,
        enforced_config_path=enforced_config_input,
        log=logger
    )

    args = SimpleNamespace(
        config_input=config_input,
        default_config_input=default_config_input,
        enforced_config_input=enforced_config_input,
        cluster_id=cluster_id,
        version=version,
        terminate=terminate,
        create=create,
        list=list,
        check=check,
        ide=ide,
        update=update,
        verbose=verbosity,
        debug=debug
    )

    if configurations:
        # You may want to pass the action as a string instead of the entire args object
        sys.exit(run_action(args, configurations, config_input))

if __name__ == "__main__":
    main()
