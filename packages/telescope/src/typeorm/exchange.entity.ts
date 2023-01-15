import { Column, Entity, PrimaryColumn } from 'typeorm';

@Entity()
export class Exchange {
  @PrimaryColumn({ type: 'bigint', name: 'id' })
  id: number;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ type: 'text'})
  config: string;

  @Column({ type: 'varchar', length: 255 })
  market_type: string;

  @Column({ type: 'varchar', length: 255 })
  status: string;
}
