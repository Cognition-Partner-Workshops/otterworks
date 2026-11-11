package com.halvergate.payments;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.arjuna.ats.internal.jta.recovery.arjunacore.XARecoveryModule;
import jakarta.jms.JMSException;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.junit.jupiter.api.Test;

class StatusXaRecoveryTest {
    @Test
    void registersUnregistersAndReturnsNoResourcesWhenBrokerIsUnavailable() throws Exception {
        var factory = mock(ActiveMQXAConnectionFactory.class);
        var module = mock(XARecoveryModule.class);
        when(factory.createXAConnection()).thenThrow(new JMSException("broker unavailable"));
        var recovery = new StatusXaRecovery(factory, module);
        recovery.register();
        verify(module).addXAResourceRecoveryHelper(recovery);
        assertThat(recovery.getXAResources()).isEmpty();
        recovery.close();
        verify(module).removeXAResourceRecoveryHelper(recovery);
    }
}
