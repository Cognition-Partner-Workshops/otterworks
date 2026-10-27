package com.otterworks.fleet.returns;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CarReturnRepository extends JpaRepository<CarReturn, Long> {

    Optional<CarReturn> findFirstByVehicle_IdOrderByReturnDateDescIdDesc(Long vehicleId);
}
