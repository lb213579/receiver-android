/*
 * Copyright (C) 2019 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 */
package org.opendroneid.android.data;

import android.content.res.Resources;

import androidx.annotation.NonNull;

import org.opendroneid.android.R;

import java.util.Locale;

public class LocationData extends MessageData {

    private StatusEnum status;
    private heightTypeEnum heightType;
    private double direction;
    private double speedHorizontal;
    private double speedVertical;
    private double latitude;
    private double longitude;
    private double altitudePressure;
    private double altitudeGeodetic;
    private double height;
    private HorizontalAccuracyEnum horizontalAccuracy;
    private VerticalAccuracyEnum verticalAccuracy;
    private VerticalAccuracyEnum baroAccuracy;
    private SpeedAccuracyEnum speedAccuracy;
    private double locationTimestamp;
    private double timeAccuracy;
    private float distance;

    public LocationData() {
        super();
        status = StatusEnum.Undeclared;
        heightType = heightTypeEnum.Takeoff;
        direction = 361; // 361 is the Invalid value in the specification
        speedHorizontal = 255; // 255 is the Invalid value in the specification
        speedVertical = 63; // 63 is the Invalid value in the specification
        latitude = 0;
        longitude = 0;
        altitudePressure = -1000; // -1000 is the Invalid value in the specification
        altitudeGeodetic = -1000; // -1000 is the Invalid value in the specification
        height = -1000; // -1000 is the Invalid value in the specification
        horizontalAccuracy = HorizontalAccuracyEnum.Unknown;
        verticalAccuracy = VerticalAccuracyEnum.Unknown;
        baroAccuracy = VerticalAccuracyEnum.Unknown;
        speedAccuracy = SpeedAccuracyEnum.Unknown;
        locationTimestamp = 0xFFFF; // 0xFFFF is the Invalid value in the specification
        timeAccuracy = 0;
    }

    public enum StatusEnum {
        Undeclared,
        Ground,
        Airborne,
        Emergency,
        Remote_ID_System_Failure  { @NonNull public String toString() { return "Rem_ID_Sys_Fail"; } },
    }
    public StatusEnum getStatus() { return status; }
    public void setStatus(int status) {
        this.status = switch (status) {
            case 1 -> StatusEnum.Ground;
            case 2 -> StatusEnum.Airborne;
            case 3 -> StatusEnum.Emergency;
            case 4 -> StatusEnum.Remote_ID_System_Failure;
            default -> StatusEnum.Undeclared;
        };
    }

    public enum heightTypeEnum {
        Takeoff,
        Ground,
    }
    public heightTypeEnum getHeightType() { return heightType; }
    public void setHeightType(int heightType) {
        if (heightType == 1)
            this.heightType = heightTypeEnum.Ground;
        else
            this.heightType = heightTypeEnum.Takeoff;
    }

    public double getDirection() { return direction; }
    public String getDirectionAsString(Resources res) {
        if (direction != 361)
            return String.format(Locale.US,"%3.0f deg", direction);
        else
            return res.getString(R.string.unknown);
    }
    public void setDirection(double direction) {
        this.direction = (direction < 0 || direction > 360) ? 361 : direction;
    }

    public double getSpeedHorizontal() { return speedHorizontal; }
    public String getSpeedHorizontalAsString(Resources res) {
        if (speedHorizontal != 255)
            return String.format(Locale.US,"%3.2f m/s", speedHorizontal);
        else
            return res.getString(R.string.unknown);
    }
    public String getSpeedHorizontalLessPreciseAsString(Resources res) {
        if (speedHorizontal != 255)
            return String.format(Locale.US,"%3.0fm/s", speedHorizontal);
        else
            return res.getString(R.string.unknown);
    }
    public void setSpeedHorizontal(double speedHorizontal) {
        double speed = speedHorizontal;
        if (speed < 0 || speed > 254.25)
            speed = 255; // 255 is defined in the specification as the Invalid value
        this.speedHorizontal = speed;
    }

    public double getSpeedVertical() { return speedVertical; }
    public String getSpeedVerticalAsString(Resources res) {
        if (speedVertical != 63)
            return String.format(Locale.US,"%3.2f m/s", speedVertical);
        else
            return res.getString(R.string.unknown);
    }
    public void setSpeedVertical(double speedVertical) {
        double speed = speedVertical;
        if (speed < -62 || speed > 62)
            speed = 63; // 63 is defined in the specification as the Invalid value
        this.speedVertical = speed;
    }

    public double getLatitude() { return latitude; }
    public String getLatitudeAsString(Resources res) {
        if (latitude == 0 && longitude == 0)
            return res.getString(R.string.unknown);
        return String.format(Locale.US,"%3.7f", latitude);
    }
    public void setLatitude(double latitude) {
        double lat = latitude;
        if (lat < -90 || lat > 90) {
            lat = 0;
            this.longitude = 0; // both equal to zero is defined in the specification as the Invalid value
        }
        this.latitude = lat;
    }

    public double getLongitude() { return longitude; }
    public String getLongitudeAsString(Resources res) {
        if (latitude == 0 && longitude == 0)
            return res.getString(R.string.unknown);
        return String.format(Locale.US,"%3.7f", longitude);
    }
    public void setLongitude(double longitude) {
        double lon = longitude;
        if (lon < -180 || lon > 180) {
            this.latitude = 0;
            lon = 0; // both equal to zero is defined in the specification as the Invalid value
        }
        this.longitude = lon;
    }

    private String getAltitudeAsString(double altitude, Resources res) {
        if (altitude == -1000)
            return res.getString(R.string.unknown);
        return String.format(Locale.US,"%3.1f m", altitude);
    }
    public double getAltitudePressure() { return altitudePressure; }
    public String getAltitudePressureAsString(Resources res) { return getAltitudeAsString(altitudePressure, res); }
    public void setAltitudePressure(double altitudePressure) {
        double alt = altitudePressure;
        if (alt < -1000 || alt > 31767)
            alt = -1000; // -1000 is defined in the specification as the Invalid value
        this.altitudePressure = alt;
    }
    public double getAltitudeGeodetic() { return altitudeGeodetic; }
    public String getAltitudeGeodeticAsString(Resources res) { return getAltitudeAsString(altitudeGeodetic, res); }
    public void setAltitudeGeodetic(double altitudeGeodetic) {
        double alt = altitudeGeodetic;
        if (alt < -1000 || alt > 31767)
            alt = -1000; // -1000 is defined in the specification as the Invalid value
        this.altitudeGeodetic = alt;
    }
    public double getHeight() { return height; }
    public String getHeightAsString(Resources res) { return getAltitudeAsString(height, res); }
    public String getHeightLessPreciseAsString(Resources res) {
        if (height == -1000)
            return res.getString(R.string.unknown);
        return String.format(Locale.US,"%3.0fm", height);
    }
    public void setHeight(double height) {
        double h = height;
        if (h < -1000 || h > 31767)
            h = -1000; // -1000 is defined in the specification as the Invalid value
        this.height = h;
    }

    public enum HorizontalAccuracyEnum {
        Unknown,
        kilometers_18_52,
        kilometers_7_408,
        kilometers_3_704,
        kilometers_1_852,
        meters_926,
        meters_555_6,
        meters_185_2,
        meters_92_6,
        meters_30,
        meters_10,
        meters_3,
        meters_1,
    }
    public HorizontalAccuracyEnum getHorizontalAccuracy() { return horizontalAccuracy; }
    public String getHorizontalAccuracyAsString(Resources res) {
        return switch (horizontalAccuracy) {
            case kilometers_18_52 -> "< 18.52 km";
            case kilometers_7_408 -> "< 7.408 km";
            case kilometers_3_704 -> "< 3.704 km";
            case kilometers_1_852 -> "< 1.852 km";
            case meters_926 -> "< 926 m";
            case meters_555_6 -> "< 555.6 m";
            case meters_185_2 -> "< 185.2 m";
            case meters_92_6 -> "< 92.6 m";
            case meters_30 -> "< 30 m";
            case meters_10 -> "< 10 m";
            case meters_3 -> "< 3 m";
            case meters_1 -> "< 1 m";
            default -> res.getString(R.string.unknown);
        };
    }
    public void setHorizontalAccuracy(int horizontalAccuracy) {
        this.horizontalAccuracy = switch (horizontalAccuracy) {
            case 1 -> HorizontalAccuracyEnum.kilometers_18_52;
            case 2 -> HorizontalAccuracyEnum.kilometers_7_408;
            case 3 -> HorizontalAccuracyEnum.kilometers_3_704;
            case 4 -> HorizontalAccuracyEnum.kilometers_1_852;
            case 5 -> HorizontalAccuracyEnum.meters_926;
            case 6 -> HorizontalAccuracyEnum.meters_555_6;
            case 7 -> HorizontalAccuracyEnum.meters_185_2;
            case 8 -> HorizontalAccuracyEnum.meters_92_6;
            case 9 -> HorizontalAccuracyEnum.meters_30;
            case 10 -> HorizontalAccuracyEnum.meters_10;
            case 11 -> HorizontalAccuracyEnum.meters_3;
            case 12 -> HorizontalAccuracyEnum.meters_1;
            default -> HorizontalAccuracyEnum.Unknown;
        };
    }

    public enum VerticalAccuracyEnum {
        Unknown,
        meters_150,
        meters_45,
        meters_25,
        meters_10,
        meters_3,
        meters_1,
    }
    public VerticalAccuracyEnum getVerticalAccuracy() { return verticalAccuracy; }
    public String getVerticalAccuracyAsString(VerticalAccuracyEnum accuracy, Resources res) {
        return switch (accuracy) {
            case meters_150 -> "< 150 m";
            case meters_45 -> "< 45 m";
            case meters_25 -> "< 25 m";
            case meters_10 -> "< 10 m";
            case meters_3 -> "< 3 m";
            case meters_1 -> "< 1 m";
            default -> res.getString(R.string.unknown);
        };
    }
    private VerticalAccuracyEnum intToVerticalAccuracy(int verticalAccuracy) {
        return switch (verticalAccuracy) {
            case 1 -> VerticalAccuracyEnum.meters_150;
            case 2 -> VerticalAccuracyEnum.meters_45;
            case 3 -> VerticalAccuracyEnum.meters_25;
            case 4 -> VerticalAccuracyEnum.meters_10;
            case 5 -> VerticalAccuracyEnum.meters_3;
            case 6 -> VerticalAccuracyEnum.meters_1;
            default -> VerticalAccuracyEnum.Unknown;
        };
    }
    public void setVerticalAccuracy(int verticalAccuracy) {
        this.verticalAccuracy = intToVerticalAccuracy(verticalAccuracy);
    }
    public VerticalAccuracyEnum getBaroAccuracy() { return baroAccuracy; }
    public void setBaroAccuracy(int verticalAccuracy) {
        this.baroAccuracy = intToVerticalAccuracy(verticalAccuracy);
    }

    public enum SpeedAccuracyEnum {
        Unknown,
        meter_per_second_10,
        meter_per_second_3,
        meter_per_second_1,
        meter_per_second_0_3,
    }
    public SpeedAccuracyEnum getSpeedAccuracy() { return speedAccuracy; }
    public String getSpeedAccuracyAsString(Resources res) {
        return switch (speedAccuracy) {
            case meter_per_second_10 -> "< 10 m/s";
            case meter_per_second_3 -> "< 3 m/s";
            case meter_per_second_1 -> "< 1 m/s";
            case meter_per_second_0_3 -> "< 0.3 m/s";
            default -> res.getString(R.string.unknown);
        };
    }
    public void setSpeedAccuracy(int speedAccuracy) {
        this.speedAccuracy = switch (speedAccuracy) {
            case 1 -> SpeedAccuracyEnum.meter_per_second_10;
            case 2 -> SpeedAccuracyEnum.meter_per_second_3;
            case 3 -> SpeedAccuracyEnum.meter_per_second_1;
            case 4 -> SpeedAccuracyEnum.meter_per_second_0_3;
            default -> SpeedAccuracyEnum.Unknown;
        };
    }

    public double getLocationTimestamp() { return locationTimestamp; }
    private double getTimeStampMinutes() { return (float) (((int) (locationTimestamp / 10)) / 60); }
    private double getTimeStampSeconds() { return (locationTimestamp/10) % 60; }
    public String getLocationTimestampAsString() {
        if (locationTimestamp == 0xFFFF)
            return "--:--";

        double totalSeconds = locationTimestamp / 10.0;

        int minutes = (int)(totalSeconds / 60);
        int seconds = (int)Math.round(totalSeconds % 60);

        if (seconds == 60) {
            seconds = 0;
            minutes += 1;
        }

        return String.format(Locale.US, "%02d:%02d", minutes, seconds);
    }
    public void setLocationTimestamp(double locationTimestamp) {
        double timestamp = locationTimestamp;
        if (timestamp < 0)
            timestamp = 0;
        if (timestamp != 0xFFFF && timestamp > 36000)
            timestamp = 36000; // Max one hour is allowed. Unit is 0.1s
        this.locationTimestamp = timestamp;
    }

    public double getTimeAccuracy() { return timeAccuracy; }
    public String getTimeAccuracyAsString(Resources res) {
        if (timeAccuracy == 0)
            return res.getString(R.string.unknown);
        else
            return String.format(Locale.US,"<= %1.1f s", timeAccuracy);
    }
    public void setTimeAccuracy(double timeAccuracy) {
        double acc = timeAccuracy;
        if (acc < 0)
            acc = 0;
        if (acc > 1.5)
            acc = 1.5; // 1.5s is the maximum value in the specification
        this.timeAccuracy = acc;
    }

    public String getDistanceAsString() { return String.format(Locale.US,"~%.0f m", distance); }
    public float getDistance() { return distance; }
    public void setDistance(float distance) { this.distance = distance; }
}
