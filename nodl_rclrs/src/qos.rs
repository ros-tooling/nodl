use rclrs::{QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy};

/// Build a QoSProfile from the scalar values that nodl_generator_rust embeds
/// into generated code.  Generated callers pass string literals so there is
/// no heap allocation on the hot path.
pub fn profile_from_nodl(
    history: &str,   // "N" (depth) or "ALL"
    reliability: &str, // "RELIABLE" | "BEST_EFFORT"
    durability: &str,  // "TRANSIENT_LOCAL" | "VOLATILE" | ""
) -> QoSProfile {
    let hist = if history == "ALL" {
        QoSHistoryPolicy::KeepAll
    } else {
        let depth: usize = history.parse().unwrap_or(10);
        QoSHistoryPolicy::KeepLast { depth }
    };

    let rel = if reliability == "BEST_EFFORT" {
        QoSReliabilityPolicy::BestEffort
    } else {
        QoSReliabilityPolicy::Reliable
    };

    let dur = if durability == "TRANSIENT_LOCAL" {
        QoSDurabilityPolicy::TransientLocal
    } else {
        QoSDurabilityPolicy::Volatile
    };

    QoSProfile {
        history: hist,
        reliability: rel,
        durability: dur,
        ..QoSProfile::default()
    }
}

/// Shorthand constants for generated code.
pub fn reliable(depth: usize) -> QoSProfile {
    profile_from_nodl(&depth.to_string(), "RELIABLE", "VOLATILE")
}

pub fn best_effort(depth: usize) -> QoSProfile {
    profile_from_nodl(&depth.to_string(), "BEST_EFFORT", "VOLATILE")
}

pub fn sensor_data() -> QoSProfile {
    best_effort(5)
}
