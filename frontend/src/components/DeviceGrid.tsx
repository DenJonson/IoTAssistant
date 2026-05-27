import type { DeviceWithState } from "../api/types";
import { DeviceCard } from "./DeviceCard";

type DeviceGridProps = {
    devices: DeviceWithState[];
};

export function DeviceGrid({ devices }: DeviceGridProps) {
    return (
        <section className="devices-grid">
            {devices.map((item) => (
                <DeviceCard item={item} key={item.device.device_id} />
            ))}
        </section>
    );
}