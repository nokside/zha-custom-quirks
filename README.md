[Home Assistant ZHA Documentation](https://www.home-assistant.io/integrations/zha/)

# Installation

1. Create a directory for custom quirks (e.g., `/config/zha_custom_quirks/`).

2. Add the following to your `configuration.yaml`:

   ```yaml
   zha:
     custom_quirks_path: /config/zha_custom_quirks/
   ```

3. Copy the required `.py` files into the directory you created.

4. Restart Home Assistant or reload ZHA.

5. Reconfigure or re-pair the device if needed to apply the new quirk.

---

<details>
<summary>Additional ZHA Tips</summary>

Some optional ZHA settings that may improve compatibility and functionality in certain Zigbee networks.

```yaml
zha:
  zigpy_config:
    source_routing: true # May improve routing in some larger Zigbee networks.
    ezsp_policies:
      TRUST_CENTER_POLICY: 0x0002 # Required for certain devices, such as Philips Hue Motion Sensors (SML001/SML002).
    ota:
      extra_providers:
        - type: z2m # Zigbee2MQTT OTA firmware updates.
```
</details>
