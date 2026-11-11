// Rydd DOM-et mellom testene. Testing Library gjør det selv bare når `afterEach` er global;
// her er vitest-globalene av, så det registreres eksplisitt.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);
