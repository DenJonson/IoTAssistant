import ReactECharts from "echarts-for-react";
import type { MeasurementPoint } from "../../api/types";

type Props = {
    points: MeasurementPoint[];
    unit: string | null;
}

export function MetricsEChart({
    points,
    unit,
}: Props) {
    const option = {
        tooltip: {
            trigger: "axis",
        },
        dataZoom: [
            {
                type: "inside",
            },
            {
                type: "slider",
            },
        ],
        legend: {
            data: ['metric'],
        },
        grid: {
            left: 50,
            right: 20,
            top: 20,
            bottom: 40,
        },
        xAxis: {
            type: "time",
        },
        yAxis: {
            type: "value",
            name: unit ?? "",
        },

        series: [
            {
                type: "line",
                smooth: true,
                data: points.map((p) => [
                    p.ts,
                    p.value,
                ]),
            },
        ],
    };

    return (
        <ReactECharts
            option={option}
            style={{
                height: 400,
            }}
        />
    );
}