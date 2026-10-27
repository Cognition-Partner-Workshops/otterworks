package com.otterworks.fleet.returns;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/returns")
public class ReturnsController {

    private final ReturnsService returnsService;

    public ReturnsController(ReturnsService returnsService) {
        this.returnsService = returnsService;
    }

    @GetMapping("/lookup")
    public ReturnCandidate lookup(
            @RequestParam(name = "plate", required = false) String plate,
            @RequestParam(name = "vehicleId", required = false) Long vehicleId) {
        return returnsService.lookup(plate, vehicleId);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ReturnView submit(@RequestBody ReturnRequest request) {
        return returnsService.returnCar(request);
    }
}
