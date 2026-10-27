package com.otterworks.fleet.api;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.config.ProfileResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/profile")
@Tag(name = "Profile", description = "Active country configuration")
public class ProfileController {

    private final CountryProfile countryProfile;

    public ProfileController(CountryProfile countryProfile) {
        this.countryProfile = countryProfile;
    }

    @GetMapping
    @Operation(summary = "Get the active country profile")
    public ProfileResponse getProfile() {
        return ProfileResponse.from(countryProfile);
    }
}
