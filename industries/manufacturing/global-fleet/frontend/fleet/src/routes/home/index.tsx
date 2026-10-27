import { Link } from 'react-router'

export default function Home() {
  return (
    <section>
      <h1>Global Fleet</h1>
      <p>Company-car services for employees.</p>
      <ul>
        <li><Link to="/eligibility">Employee search</Link></li>
        <li><Link to="/assignment">Car request</Link></li>
        <li><Link to="/assignment">Current car and history</Link></li>
        <li><Link to="/returns">Return a car</Link></li>
        <li><Link to="/mileage">Mileage claim</Link></li>
        <li><Link to="/mileage/approvals">Mileage approvals</Link></li>
        <li><Link to="/benefit?view=inquiry">Benefit inquiry</Link></li>
        <li><Link to="/benefit?view=statement">Benefit statement</Link></li>
        <li><Link to="/benefit?view=periods">Period close</Link></li>
      </ul>
    </section>
  )
}
