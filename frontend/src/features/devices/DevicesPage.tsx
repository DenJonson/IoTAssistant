import type { DeviceWithState } from "../../api/types";
import { DeviceGrid } from "./DeviceGrid";

type DevicesPageProps = {
    devices: DeviceWithState[];
};

export function DevicesPage({ devices }: DevicesPageProps) {
    return (
        <section className="devices-page">
            <div className="section-header">
                <h2>Devices</h2>
                <p>Known devices and their latest current state.</p>
            </div>

            <DeviceGrid devices={devices} />
        </section>
    );
}