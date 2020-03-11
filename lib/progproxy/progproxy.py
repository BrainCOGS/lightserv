from os import environ
import logging
import requests
import json

logger = logging.getLogger("progproxy")


class progproxy(object):
    def __init__(
        self,
        target_hname="localhost",
        target_port="8001",
        key=environ["CONFIGPROXY_AUTH_TOKEN"],
        target_protocol="http",
    ):
        logger.debug("Programable Proxy Object Created")
        self.target = f"{target_protocol}://{target_hname}:{target_port}"
        self.headers = {"Authorization": f"token {key}"}
        logger.debug(f"Target set to {self.target}")
        logger.debug(f"header set to {self.headers}")

    def addroute(self, proxypath, proxytarget):
        logger.debug(f"adding path {proxypath} pointing to {proxytarget}")
        req_data = {"target": proxytarget}
        response = requests.post(
            f"{self.target}/api/routes/{proxypath}", data=json.dumps(req_data), headers=self.headers
        )
        if response.status_code == 204 or response.status_code == 201:
            logger.debug("path added successfully")
        else:
            logger.warn(
                f"failed to add proxy path {proxypath} pointing to {proxytarget}"
            )
            logger.debug(f"requests returned: {response}")

    def deleteroute(self, proxypath):
        logger.debug(f"removing proxy path {proxypath}")
        response = requests.delete(f"{self.target}/api/routes{proxypath}",headers=self.headers)
        if response.status_code != 204:
            logger.warn(f"removal of {proxypath} failed")
            logger.debug(f"requests returned: {response}")
        else:
            logger.debug(f"{proxypath} removed")

    def getroutes(self,inactive_since=None):
        """ inactive_since is a ISO 8601 timestamp, e.g.:
        2020-01-28T18:11:57.026018 """
        logger.debug("getting configured routes")
        if inactive_since is not None:
            response = requests.get(f"{self.target}/api/routes?inactive_since={inactive_since}",headers=self.headers)
        else:
            response = requests.get(f"{self.target}/api/routes",headers=self.headers)

        logger.debug(f"current routes: {response.text}")

        return response
