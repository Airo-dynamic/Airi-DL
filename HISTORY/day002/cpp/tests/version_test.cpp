#include "airidl/version.hpp"

#include <iostream>

int main() {
    if (airidl::kProjectName != "Airi-DL" || airidl::kSnapshot != "day002" ||
        airidl::Version() != "0.1.0.dev1") {
        std::cerr << "Airi-DL version contract failed\n";
        return 1;
    }
    return 0;
}
