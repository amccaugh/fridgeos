#%%
import requests

class StateMachineClient:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url.rstrip("/")

    def get_state(self):
        """Get the current state from the server (just the state string)."""
        resp = requests.get(f"{self.base_url}/state")
        resp.raise_for_status()
        data = resp.json()
        return data["current_state"]

    def set_state(self, state):
        """Set the state on the server. Returns None if successful, raises an error if not."""
        resp = requests.put(
            f"{self.base_url}/state",
            json={"state": state},
            headers={"Content-Type": "application/json"}
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Try to extract the error message from the response
            try:
                error_detail = resp.json().get("detail", str(e))
            except Exception:
                error_detail = str(e)
            raise RuntimeError(f"Failed to set state: {error_detail}") from e
        return None


if __name__ == "__main__":
    state_machine_client = StateMachineClient(base_url = 'http://localhost:8001')
    print(state_machine_client.get_state())
    print(state_machine_client.set_state('warm'))
    print(state_machine_client.set_state('ASDHFfjdhfafsj'))
