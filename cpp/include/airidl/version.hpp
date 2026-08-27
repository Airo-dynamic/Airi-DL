#pragma once

#include <string_view>

namespace airidl {

inline constexpr std::string_view kProjectName{"Airi-DL"};
inline constexpr std::string_view kSnapshot{"day001"};

[[nodiscard]] std::string_view Version() noexcept;

}  // namespace airidl
