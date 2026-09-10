import unittest
from unittest.mock import Mock

from create_source_swap_policies import create_policies, desired_payload


class PolicyTests(unittest.TestCase):
    def test_payload(self):
        payload = desired_payload({
            "name": "dev-prod", "fromConnectionId": "dev",
            "toConnectionUserAttributeId": "attribute",
        })
        self.assertEqual(payload["type"], "deployment")
        self.assertEqual(payload["swaps"]["deploymentSwaps"], [])
        self.assertEqual(payload["swaps"]["toConnection"]["userAttributeId"], "attribute")

    def test_dry_run_and_idempotency(self):
        client = Mock()
        client.paginate.return_value = iter([{
            "type": "deployment", "name": "existing", "fromConnectionId": "dev-1"
        }])
        config = {"policies": [
            {"name": "existing", "fromConnectionId": "dev-1", "toConnectionUserAttributeId": "ua"},
            {"name": "new", "fromConnectionId": "dev-2", "toConnectionUserAttributeId": "ua"},
        ]}
        result = create_policies(client, config, apply=False)
        self.assertEqual([row["status"] for row in result], ["exists", "would-create"])
        client.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
